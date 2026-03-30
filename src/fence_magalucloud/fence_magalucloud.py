#!/usr/bin/env python3
# fence_magalucloud.py — Fence Agent para Magalu Cloud (ClusterLabs / Pacemaker)
#
# Segue a especificação técnica do ClusterLabs:
#   https://github.com/ClusterLabs/fence-agents/blob/main/doc/fa-dev-guide.md
#   https://github.com/ClusterLabs/fence-agents/blob/main/doc/FenceAgentAPI.md
#
# Referência de implementação: fence_vmware_rest
#   https://github.com/ClusterLabs/fence-agents/blob/main/agents/vmware_rest/fence_vmware_rest.py
#
# Dependências:
#   - fence-agents-base (provê o módulo `fencing` via @FENCEAGENTSLIBDIR@)
#   - requests

import atexit
import logging
import sys

import requests

# Em produção, @FENCEAGENTSLIBDIR@ é expandido pelo autoconf para o caminho real
# (ex: /usr/share/fence). Em instalação manual, crie um symlink do fencing.py para
# o mesmo diretório do agente — o fallback abaixo o encontrará automaticamente.
sys.path.append('@FENCEAGENTSLIBDIR@')
try:
    from fencing import *  # noqa: F401, F403 — padrão obrigatório do ClusterLabs
    from fencing import (
        EC_BAD_ARGS,
        EC_LOGIN_DENIED,
        EC_STATUS,
        all_opt,
        atexit_handler,
        check_input,
        fail,
        fence_action,
        process_input,
        run_delay,
        show_docs,
    )
except ImportError:
    # Fallback: fencing.py no mesmo diretório do agente (symlink ou cópia local)
    import pathlib

    sys.path.insert(0, str(pathlib.Path(__file__).parent))
    from fencing import *  # noqa: F401, F403
    from fencing import (
        EC_BAD_ARGS,
        EC_LOGIN_DENIED,
        EC_STATUS,
        all_opt,
        atexit_handler,
        check_input,
        fail,
        fence_action,
        process_input,
        run_delay,
        show_docs,
    )

# ---------------------------------------------------------------------------
# Mapeamento de estados da API → vocabulário do fence agent
# ---------------------------------------------------------------------------
# A API do Magalu Cloud retorna o campo "state" com valores como "running",
# "stopped" ou "suspended". O fence agent espera "on" ou "off".
state = {
    'running': 'on',
    'stopped': 'off',
    'suspended': 'off',
}

HTTP_UNAUTHORIZED = 401
HTTP_FORBIDDEN = 403
HTTP_NOT_FOUND = 404


# ---------------------------------------------------------------------------
# Opções personalizadas
# ---------------------------------------------------------------------------


def define_new_opts():
    """Registra as opções específicas do Magalu Cloud no dicionário global all_opt."""

    all_opt['api_key'] = {
        'getopt': ':',
        'longopt': 'api-key',
        'help': '--api-key=[key]            Chave de API para autenticação no Magalu Cloud',
        'required': '1',
        'shortdesc': 'Chave de API do Magalu Cloud',
        'order': 1,
    }

    all_opt['region'] = {
        'getopt': ':',
        'longopt': 'region',
        'help': '--region=[region]          Região do Magalu Cloud (padrão: br-se1)',
        'required': '0',
        'shortdesc': 'Região do Magalu Cloud',
        'default': 'br-se1',
        'order': 2,
    }


# ---------------------------------------------------------------------------
# Helpers de comunicação com a API
# ---------------------------------------------------------------------------


def _base_url(options: dict) -> str:
    """Monta a URL base a partir da região configurada."""
    region = options.get('--region', 'br-se1')
    return f'https://api.magalu.cloud/{region}/compute/v1'


def _headers(options: dict) -> dict:
    """Retorna os headers HTTP obrigatórios para autenticação."""
    return {
        'x-api-key': options['--api-key'],
        'Accept': 'application/json',
    }


def _request(method: str, url: str, headers: dict, options: dict, **kwargs) -> requests.Response:
    """
    Executa uma requisição HTTP e trata erros de autenticação (401)
    de forma padronizada, encerrando via fail() do fencing.

    O timeout é lido de options["--shell-timeout"] (padrão da fencing library),
    permitindo que o operador o configure via Pacemaker sem alterar o agente.
    """
    timeout = int(options.get('--shell-timeout', 30))
    # Pacemaker 2.0+ passa disable_timeout=true, zerando --shell-timeout.
    # requests não aceita timeout=0; None significa sem limite.
    effective_timeout = timeout if timeout > 0 else None
    try:
        response = requests.request(method, url, headers=headers, timeout=effective_timeout, **kwargs)
    except requests.exceptions.RequestException as exc:
        logging.error('fence_magalucloud: erro de conexão: %s', exc)
        fail(EC_STATUS)

    if response.status_code in (HTTP_UNAUTHORIZED, HTTP_FORBIDDEN):
        logging.error(
            'fence_magalucloud: autenticação recusada (%s) — verifique --api-key',
            response.status_code,
        )
        fail(EC_LOGIN_DENIED)

    return response


# ---------------------------------------------------------------------------
# Funções obrigatórias do fence agent
# ---------------------------------------------------------------------------


def get_power_status(_conn, options: dict) -> str:
    """
    Consulta o estado de energia de uma instância.

    Parâmetros
    ----------
    conn    : não utilizado (mantido por compatibilidade com a interface do fencing)
    options : dicionário de opções; options["--plug"] contém o ID da VM

    Retorno
    -------
    "on"  — instância em execução
    "off" — instância parada ou suspensa
    """
    vm_id = options['--plug']
    url = f'{_base_url(options)}/instances/{vm_id}'
    headers = _headers(options)

    response = _request('GET', url, headers, options)

    if response.status_code == HTTP_NOT_FOUND:
        logging.error("fence_magalucloud: instância '%s' não encontrada (404)", vm_id)
        fail(EC_STATUS)

    if not response.ok:
        logging.error(
            "fence_magalucloud: erro ao obter status da instância '%s' (HTTP %s)",
            vm_id,
            response.status_code,
        )
        fail(EC_STATUS)

    data = response.json()
    vm_state = data.get('state', '')

    if vm_state not in state:
        logging.error(
            "fence_magalucloud: estado desconhecido '%s' para instância '%s'",
            vm_state,
            vm_id,
        )
        fail(EC_STATUS)

    logging.debug('fence_magalucloud: instância %s → estado=%s', vm_id, vm_state)
    return state[vm_state]


def set_power_status(_conn, options: dict) -> None:
    """
    Envia um comando de liga/desliga para uma instância.

    Parâmetros
    ----------
    conn    : não utilizado
    options : options["--action"] contém "on" ou "off";
              options["--plug"]   contém o ID da VM
    """
    vm_id = options['--plug']
    action = options['--action']
    headers = _headers(options)

    # Mapeia a ação do fencing para o endpoint da API (igual ao padrão fence_vmware_rest)
    endpoint = {'on': 'start', 'off': 'stop'}[action]

    url = f'{_base_url(options)}/instances/{vm_id}/{endpoint}'
    response = _request('POST', url, headers, options)

    if response.status_code == HTTP_NOT_FOUND:
        logging.error("fence_magalucloud: instância '%s' não encontrada (404)", vm_id)
        fail(EC_STATUS)

    if not response.ok:
        logging.error(
            "fence_magalucloud: falha ao executar '%s' na instância '%s' (HTTP %s)",
            action,
            vm_id,
            response.status_code,
        )
        fail(EC_STATUS)

    logging.debug('fence_magalucloud: ação %s executada na instância %s', action, vm_id)


def get_list(_conn, options: dict) -> dict:
    """
    Retorna um dicionário com todas as instâncias disponíveis na região.

    Utilizado pelo Pacemaker para validar que o ID da VM (--plug) existe.

    Retorno
    -------
    dict no formato { "<id>": ("<nome>", "<status>") }
    """
    url = f'{_base_url(options)}/instances'
    headers = _headers(options)

    response = _request('GET', url, headers, options)

    if not response.ok:
        logging.error(
            'fence_magalucloud: falha ao listar instâncias (HTTP %s)', response.status_code
        )
        fail(EC_STATUS)

    data = response.json()
    instances = data.get('instances', [])

    outlets = {}
    for instance in instances:
        vm_id = instance.get('id', '')
        vm_name = instance.get('name', vm_id)
        vm_state = state.get(instance.get('state', ''), 'unknown')
        outlets[vm_id] = (vm_name, vm_state)

    return outlets


# ---------------------------------------------------------------------------
# Ponto de entrada
# ---------------------------------------------------------------------------


def main():
    """
    Ponto de entrada do fence agent.

    Fluxo padrão do ClusterLabs (conforme fence_vmware_rest e fa-dev-guide.md):
      1. Registra atexit_handler (primeiro passo obrigatório)
      2. Registra opções personalizadas em all_opt
      3. Lê e valida os argumentos (stdin ou argv) — combinados em uma linha
      4. Exibe metadados/documentação se solicitado
      5. Aguarda o delay configurado (evita tempestade de fencing)
      6. Executa a ação via fence_action()
      7. Propaga o exit code via sys.exit()
    """
    # 1. Registra o handler de saída — deve ser o primeiro passo (padrão ClusterLabs)
    atexit.register(atexit_handler)

    # 2. Registra as opções específicas do Magalu Cloud
    define_new_opts()

    # Opções que este fence agent suporta
    device_opt = [
        'api_key',
        'region',
        'port',  # --plug: ID da VM (mapeado internamente como "port")
        'no_password',  # autenticação por API key, sem senha tradicional
    ]

    # 3. Lê e valida os parâmetros em uma única linha (padrão fa-dev-guide.md)
    options = check_input(device_opt, process_input(device_opt))

    # 4. Metadados exibidos pelo Pacemaker ao consultar o agente (-o metadata)
    # Executado antes da validação de --api-key para que --help e -o metadata
    # funcionem sem credenciais (padrão ClusterLabs)
    docs = {
        'shortdesc': 'Fence agent para instâncias de VM no Magalu Cloud',
        'longdesc': (
            'fence_magalucloud é um fence agent que interage com a API REST do '
            'Magalu Cloud para gerenciar o estado de energia de instâncias de '
            'máquinas virtuais. Suporta as ações: on, off, reboot, status e list.'
        ),
        'vendorurl': 'https://magalu.cloud',
    }
    show_docs(options, docs)

    # check_input não valida opções customizadas com required='1' — validar explicitamente
    # (após show_docs para que --help e -o metadata não exijam --api-key)
    if not options.get('--api-key'):
        logging.error('fence_magalucloud: --api-key é obrigatório')
        sys.exit(EC_BAD_ARGS)

    # 5. Aguarda o delay de fencing (configurável via --delay)
    run_delay(options)

    # 6. Executa a ação solicitada (on/off/reboot/status/list/monitor)
    # conn=None pois não há sessão persistente — cada chamada HTTP é independente
    result = fence_action(None, options, set_power_status, get_power_status, get_list)

    # 7. Propaga o exit code ao Pacemaker (crítico — sem isso o agente sempre retorna 0)
    sys.exit(result)


if __name__ == '__main__':
    main()
