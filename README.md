# Magalu Cloud Pacemaker Fence

Fence agent para instâncias de máquinas virtuais no **Magalu Cloud**, compatível com
[ClusterLabs](https://clusterlabs.org/) / [Pacemaker](https://clusterlabs.org/projects/pacemaker/) /
[Corosync](https://corosync.github.io/corosync/).

---

## O que é

`fence_magalucloud` é um **fence agent** — um programa chamado pelo Pacemaker para isolar
forcosamente um nó não-responsivo do cluster antes de permitir que os serviços sejam
reiniciados em outro nó. Essa técnica é conhecida como **STONITH** (_Shoot The Other Node In
The Head_) e é o mecanismo que protege clusters de alta disponibilidade contra _split-brain_
(dois nós acreditando ser o primário simultaneamente, corrompendo dados compartilhados).

O agente implementa o contrato da [Fence Agent API](https://github.com/ClusterLabs/fence-agents/blob/main/doc/FenceAgentAPI.md)
do ClusterLabs, seguindo o [guia oficial de desenvolvimento](https://github.com/ClusterLabs/fence-agents/blob/main/doc/fa-dev-guide.md)
e tomando como referência de implementação o
[fence_vmware_rest](https://github.com/ClusterLabs/fence-agents/blob/main/agents/vmware_rest/fence_vmware_rest.py).

---

## Objetivo

Permitir que um cluster Pacemaker gerencie o estado de energia de VMs hospedadas no
Magalu Cloud via API REST, executando as ações:

| Ação | O que faz |
|---|---|
| `status` | Consulta o estado de energia da VM (`on` / `off`) |
| `on` | Liga a VM (chama o endpoint `/start`) |
| `off` | Desliga a VM (chama o endpoint `/stop`) |
| `reboot` | Desliga e liga a VM |
| `list` | Lista todas as instâncias disponíveis na região |
| `monitor` | Verifica se o device de fencing está acessível |
| `metadata` | Exibe os metadados XML do agente para o Pacemaker |

---

## Como funciona

### Fluxo de invocação

O Pacemaker invoca o agente como um processo filho do daemon `pacemaker-fenced`. Os
parâmetros são passados via **stdin** (quando invocado pelo Pacemaker) ou via **argumentos
de linha de comando** (quando testado manualmente). A biblioteca `fencing` detecta
automaticamente qual modo usar: se `sys.argv` tiver argumentos, usa a linha de comando;
caso contrário, lê o stdin linha a linha no formato `chave=valor`.

```
Pacemaker (pacemaker-fenced)
    │
    ├── fork/exec: fence_magalucloud
    │       │
    │       ├── stdin: action=off\nplug=<vm-id>\napi-key=<key>\n...
    │       │
    │       └── exit code: 0 (sucesso) | != 0 (falha)
    │
    └── interpreta o exit code e registra no CIB
```

### Fluxo interno do agente

```
main()
  │
  ├── 1. atexit.register(atexit_handler)   — handler de saída (obrigatório, primeiro passo)
  ├── 2. define_new_opts()                 — registra --api-key e --region em all_opt
  ├── 3. check_input(process_input(...))   — lê e valida parâmetros (stdin ou argv)
  ├── 4. show_docs(options, docs)          — exibe metadata/help se solicitado
  ├── 5. run_delay(options)                — aguarda delay configurado (anti-tempestade)
  ├── 6. fence_action(...)                 — despacha para get/set_power_status ou get_list
  └── 7. sys.exit(result)                  — propaga o exit code ao Pacemaker
```

### Comunicação com a API do Magalu Cloud

| Ação | Método | Endpoint |
|---|---|---|
| Consultar status | `GET` | `https://api.magalu.cloud/{region}/compute/v1/instances/{vm-id}` |
| Ligar VM | `POST` | `https://api.magalu.cloud/{region}/compute/v1/instances/{vm-id}/start` |
| Desligar VM | `POST` | `https://api.magalu.cloud/{region}/compute/v1/instances/{vm-id}/stop` |
| Listar instâncias | `GET` | `https://api.magalu.cloud/{region}/compute/v1/instances` |

Autenticação via header `x-api-key`. Região padrão: `br-se1`.

### Mapeamento de estados

| Estado da API | Estado do fence agent |
|---|---|
| `running` | `on` |
| `stopped` | `off` |
| `suspended` | `off` |

### Exit codes

| Código | Constante | Significado |
|---|---|---|
| `0` | `EC_OK` | Sucesso |
| `1` | `EC_GENERIC_ERROR` | Erro genérico |
| `2` | `EC_BAD_ARGS` | Argumentos inválidos |
| `3` | `EC_LOGIN_DENIED` | Autenticação recusada (401) |
| `4` | `EC_CONNECTION_LOST` | Conexão perdida |
| `5` | `EC_TIMED_OUT` | Timeout de conexão |
| `8` | `EC_STATUS` | Falha ao obter status da VM |

---

## Requisitos para produção

### Requisitos gerais

- Python 3.11 ou superior
- Biblioteca `requests` >= 2.28
- Chave de API do Magalu Cloud com permissões de leitura e controle de VMs
- Acesso de rede entre os nós do cluster e `api.magalu.cloud` (porta 443/HTTPS)

### Debian / Ubuntu

```bash
sudo apt-get update
sudo apt-get install -y pacemaker corosync pcs fence-agents-common python3-requests
```

> `fence-agents-common` provê a biblioteca `fencing.py` em `/usr/share/fence/`.
> Se não estiver disponível no repositório, copie o arquivo `src/fence_magalucloud/fencing.py`
> para o mesmo diretório do agente.

Habilitar e iniciar o daemon `pcsd`:

```bash
sudo systemctl enable --now pcsd
sudo passwd hacluster   # definir a mesma senha em todos os nós
```

### Red Hat / Rocky Linux / AlmaLinux

Ativar o repositório de Alta Disponibilidade:

```bash
sudo dnf config-manager --set-enabled highavailability
sudo dnf install -y pacemaker pcs psmisc policycoreutils-python3 fence-agents-all python3-requests
sudo systemctl enable --now pcsd
sudo passwd hacluster
```

---

## Instalação do agente

### Opção A — Instalação via pip (recomendada)

```bash
sudo pip install fence-magalucloud
```

O agente é instalado em `/usr/local/bin/fence_magalucloud` (ou no `bin/` do virtualenv).

### Opção B — Instalação manual

Certifique-se de que `python3` e `python3-requests` estão instalados no nó:

```bash
# Debian/Ubuntu
sudo apt-get install -y python3 python3-requests

# Red Hat / Rocky / AlmaLinux
sudo dnf install -y python3 python3-requests
```

Copie o agente e a biblioteca `fencing.py` inclusa no projeto:

```bash
# Instalar o agente
sudo install -m 0755 src/fence_magalucloud/fence_magalucloud.py /usr/sbin/fence_magalucloud

# Instalar a biblioteca fencing do projeto (sem depender de pacotes do SO)
sudo install -m 0644 src/fence_magalucloud/fencing.py /usr/sbin/fencing.py
```

> A `fencing.py` inclusa no projeto já tem as correções de compatibilidade com Python 3.12+
> (escape sequences em regex), eliminando os `SyntaxWarning` gerados pela versão
> empacotada nas distribuições. Não é necessário instalar `fence-agents-common` ou
> `fence-agents-all`.

Verifique que o agente responde aos metadados:

```bash
sudo /usr/sbin/fence_magalucloud -o metadata
```

A saída deve ser um documento XML com os parâmetros `api-key`, `region`, `port` e demais
opções padrão do fencing.

---

## Configuração em um cluster Pacemaker

### 1. Inicializar o cluster (executar em um nó apenas)

```bash
# Autenticar os nós
sudo pcs host auth node1 node2

# Criar o cluster
sudo pcs cluster setup mycluster node1 addr=192.168.1.101 node2 addr=192.168.1.102

# Iniciar em todos os nós
sudo pcs cluster start --all
sudo pcs cluster enable --all
```

### 2. Verificar o estado do cluster

```bash
sudo pcs status
```

Saída esperada (sem fencing ainda):

```
Cluster name: mycluster
Status of pacemakerd: 'Pacemaker is running' (last updated ...)
Cluster Summary:
  * Stack: corosync (Pacemaker is running)
  * Current DC: node1 ...
  * 2 nodes configured, 0 resource instances configured
  * No stonith devices and stonith-enabled is not false

Node List:
  * Online: [ node1 node2 ]
```

### 3. Criar o recurso de fencing

```bash
sudo pcs stonith create fence-magalucloud fence_magalucloud \
    api-key="<SUA_API_KEY>" \
    region="br-se1" \
    pcmk_host_map="node1:<vm-id-node1>;node2:<vm-id-node2>" \
    pcmk_reboot_action="off" \
    op monitor interval=60s timeout=30s
```

Parâmetros:

| Parâmetro | Descrição | Obrigatório |
|---|---|---|
| `api-key` | Chave de API do Magalu Cloud | Sim |
| `region` | Região da API (padrão: `br-se1`) | Não |
| `pcmk_host_map` | Mapa `nome-do-nó:vm-id` | Sim |
| `pcmk_reboot_action` | Ação usada no reboot (`off` recomendado) | Não |
| `pcmk_host_list` | Lista de nós controlados pelo device | Não |
| `shell_timeout` | Timeout HTTP em segundos (padrão: 30) | Não |
| `delay` | Delay antes da ação (anti-tempestade) | Não |

### 4. Habilitar o STONITH no cluster

```bash
sudo pcs property set stonith-enabled=true
```

### 5. Verificar o recurso de fencing

```bash
sudo pcs stonith
```

Saída esperada:

```
  * fence-magalucloud    (stonith:fence_magalucloud):    Started node1
```

```bash
sudo pcs status resources
```

Saída esperada:

```
  * fence-magalucloud    (stonith:fence_magalucloud):    Started node1
```

---

## Como testar em um cluster Pacemaker

### Teste 1 — Metadata (sem credenciais)

Verifica que o agente está instalado e responde corretamente:

```bash
sudo /usr/sbin/fence_magalucloud -o metadata
```

Saída esperada:

```xml
<?xml version="1.0" ?>
<resource-agent name="fence_magalucloud" shortdesc="Fence agent para instâncias de VM no Magalu Cloud" >
<longdesc>fence_magalucloud é um fence agent que interage com a API REST do Magalu Cloud para gerenciar o estado de energia de instâncias de máquinas virtuais. Suporta as ações: on, off, reboot, status e list.</longdesc>
<vendor-url>https://magalu.cloud</vendor-url>
<parameters>
        <parameter name="action" unique="0" required="1">
                <getopt mixed="-o, --action=[action]" />
                <content type="string" default="reboot"  />
                <shortdesc lang="en">Fencing action</shortdesc>
        </parameter>
        <parameter name="api_key" unique="0" required="1">
                <getopt mixed="--api-key=[key]" />
                <content type="string"  />
                <shortdesc lang="en">Chave de API do Magalu Cloud</shortdesc>
        </parameter>
        <parameter name="plug" unique="0" required="1" obsoletes="port">
                <getopt mixed="-n, --plug=[id]" />
                <content type="string"  />
                <shortdesc lang="en">Physical plug number on device, UUID or identification of machine</shortdesc>
        </parameter>
        <parameter name="region" unique="0" required="0">
                <getopt mixed="--region=[region]" />
                <content type="string" default="br-se1"  />
                <shortdesc lang="en">Região do Magalu Cloud</shortdesc>
        </parameter>
        <parameter name="delay" unique="0" required="0">
                <getopt mixed="--delay=[seconds]" />
                <content type="second" default="0"  />
                <shortdesc lang="en">Wait X seconds before fencing is started</shortdesc>
        </parameter>
        <parameter name="shell_timeout" unique="0" required="0">
                <getopt mixed="--shell-timeout=[seconds]" />
                <content type="second" default="3"  />
                <shortdesc lang="en">Wait X seconds for cmd prompt after issuing command</shortdesc>
        </parameter>
        ...
</parameters>
<actions>
        <action name="on" automatic="0"/>
        <action name="off" />
        <action name="reboot" />
        <action name="status" />
        <action name="list" />
        <action name="list-status" />
        <action name="monitor" />
        <action name="metadata" />
        <action name="manpage" />
        <action name="validate-all" />
</actions>
</resource-agent>
```

### Teste 2 — Help

```bash
sudo /usr/sbin/fence_magalucloud --help
```

Saída esperada:

```
Usage:
	fence_magalucloud [options]

Options:
   -o, --action=[action]          Fencing action (default: reboot)
       --api-key=[key]            Chave de API para autenticação no Magalu Cloud
   -n, --plug=[id]                ID da VM (UUID da instância no Magalu Cloud)
       --region=[region]          Região do Magalu Cloud (padrão: br-se1)
       --delay=[seconds]          Wait X seconds before fencing is started (default: 0)
       --shell-timeout=[seconds]  Wait X seconds for cmd prompt after issuing command (default: 3)
   -v, --verbose                  Verbose mode
   -D, --debug-file=[debugfile]   Write debug information to given file
   -V, --version                  Display version information and exit
   -h, --help                     Display help and exit
```

### Teste 3 — Status via stdin (simula o Pacemaker)

```bash
echo "action=status
api-key=<SUA_API_KEY>
plug=<VM_ID>
region=br-se1" | sudo /usr/sbin/fence_magalucloud
```

Saída esperada: `Status: ON` ou `Status: OFF` com exit code `0`.

### Teste 4 — Status via linha de comando

```bash
sudo /usr/sbin/fence_magalucloud \
    --action=status \
    --api-key=<SUA_API_KEY> \
    --plug=<VM_ID> \
    --region=br-se1
```

### Teste 5 — Listar instâncias

```bash
sudo /usr/sbin/fence_magalucloud \
    --action=list \
    --api-key=<SUA_API_KEY> \
    --region=br-se1
```

Saída esperada:

```
<vm-id-1>,<nome-1>,on
<vm-id-2>,<nome-2>,off
```

### Teste 6 — Monitor (verifica acessibilidade da API)

```bash
sudo /usr/sbin/fence_magalucloud \
    --action=monitor \
    --api-key=<SUA_API_KEY> \
    --region=br-se1
```

Saída esperada: exit code `0` (API acessível).

### Teste 7 — Fencing via pcs (requer cluster ativo)

> **Atenção:** este comando executa o fencing real do nó. Execute apenas em ambiente de testes
> com uma VM dedicada.

```bash
# Parar o cluster no nó alvo (simula nó não-responsivo)
sudo pcs cluster stop node2

# Executar o fencing a partir do nó primário
sudo pcs stonith fence node2
```

Saída esperada:

```
Node: node2 fenced
```

Verificar no log do Pacemaker:

```bash
sudo journalctl -u pacemaker --since "5 minutes ago" | grep -i fence
```

Saída esperada (trecho):

```
pacemaker-fenced  fence_magalucloud: ação off executada na instância <vm-id>
pacemaker-controld  Node node2 was successfully fenced by node1
```

Após o teste, reiniciar o cluster no nó fenced:

```bash
sudo pcs cluster start node2
```

### Teste 8 — stonith_admin (diagnóstico avançado)

Listar todos os devices de fencing registrados:

```bash
sudo stonith_admin -L
```

Consultar o status de um nó via o device:

```bash
sudo stonith_admin -Q -r fence-magalucloud -t node2
```

Forçar fencing manual de um nó:

```bash
sudo stonith_admin -F node2
```

---

## Validação da saúde do cluster com fencing ativo

### Estado completo do cluster

```bash
sudo pcs status
```

Saída esperada com fencing configurado e cluster saudável:

```
Cluster name: mycluster
Status of pacemakerd: 'Pacemaker is running' (last updated ...)
Cluster Summary:
  * Stack: corosync (Pacemaker is running)
  * Current DC: node1 (version ...) - partition with quorum
  * 2 nodes configured, 1 resource instance configured

Node List:
  * Online: [ node1 node2 ]

Full List of Resources:
  * fence-magalucloud    (stonith:fence_magalucloud):    Started node1

Daemon Status:
  corosync: active/enabled
  pacemaker: active/enabled
  pcsd: active/enabled
```

### Verificar configuração sem erros

```bash
sudo pcs cluster verify --full
```

Saída esperada: nenhuma saída (sem erros).

### Verificar comunicação Corosync

```bash
sudo corosync-cfgtool -s
```

Saída esperada:

```
Printing ring status.
Local node ID 1
RING ID 0
	id	= 192.168.1.101
	status	= ring 0 active with no faults
```

### Verificar processos do Pacemaker

```bash
sudo ps axf | grep pacemaker
```

Saída esperada — os 7 daemons ativos:

```
pacemakerd
 └─ pacemaker-based        (CIB manager)
 └─ pacemaker-fenced       (fencing manager)
 └─ pacemaker-execd        (executor de agentes)
 └─ pacemaker-attrd        (atributos de nós)
 └─ pacemaker-schedulerd   (scheduler de recursos)
 └─ pacemaker-controld     (controlador do cluster)
```

---

## Desenvolvimento

### Configurar o ambiente

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

### Executar os testes unitários

```bash
.venv/bin/pytest tests/unit/ -v
```

### Pipeline de qualidade obrigatório (ver [CONTRACT.md](CONTRACT.md))

```bash
.venv/bin/ruff format . && .venv/bin/ruff check --fix . && .venv/bin/pyright
```

Saída esperada:

```
1 file left unchanged
All checks passed!
0 errors, 0 warnings, 0 informations
```

---

## Referências

- [ClusterLabs Fence Agent Developer Guide](https://github.com/ClusterLabs/fence-agents/blob/main/doc/fa-dev-guide.md)
- [ClusterLabs Fence Agent API](https://github.com/ClusterLabs/fence-agents/blob/main/doc/FenceAgentAPI.md)
- [fence_vmware_rest — referência de implementação](https://github.com/ClusterLabs/fence-agents/blob/main/agents/vmware_rest/fence_vmware_rest.py)
- [Pacemaker — Clusters from Scratch](https://clusterlabs.org/projects/pacemaker/doc/3.0/Clusters_from_Scratch/singlehtml/)
- [Pacemaker Administration](https://clusterlabs.org/projects/pacemaker/doc/3.0/Pacemaker_Administration/singlehtml/)
- [Pacemaker Explained](https://clusterlabs.org/projects/pacemaker/doc/3.0/Pacemaker_Explained/singlehtml/)
- [Magalu Cloud API](https://magalu.cloud)
