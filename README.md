# Magalu Cloud Pacemaker Fence

Fence agent para instâncias de máquinas virtuais no **Magalu Cloud**, compatível com
[ClusterLabs](https://clusterlabs.org/) / [Pacemaker](https://clusterlabs.org/projects/pacemaker/) /
[Corosync](https://corosync.github.io/corosync/).

---

## O que é

`fence_magalucloud` é um **fence agent** — um programa chamado pelo Pacemaker para isolar
forçosamente um nó não-responsivo do cluster antes de permitir que os serviços sejam
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
| `3` | `EC_LOGIN_DENIED` | Autenticação recusada (401/403) |
| `4` | `EC_CONNECTION_LOST` | Conexão perdida |
| `5` | `EC_TIMED_OUT` | Timeout de conexão |
| `8` | `EC_STATUS` | Falha ao obter status da VM |

---

## Instalação

Consulte [INSTALL.md](INSTALL.md) para o guia completo de configuração de cluster Pacemaker
(2 nós, Ubuntu 24.04) e instalação do `fence_magalucloud`.

---

## Testes

Consulte [TESTING.md](TESTING.md) para o guia completo de testes: ambiente local de
desenvolvimento, cluster sem Pacemaker e integração com Pacemaker.

---

## Contribuindo

Consulte [CONTRIBUTING.md](CONTRIBUTING.md) para configurar o ambiente de desenvolvimento,
executar os testes unitários e o pipeline de qualidade.

---

## Referências

- [ClusterLabs Fence Agent Developer Guide](https://github.com/ClusterLabs/fence-agents/blob/main/doc/fa-dev-guide.md)
- [ClusterLabs Fence Agent API](https://github.com/ClusterLabs/fence-agents/blob/main/doc/FenceAgentAPI.md)
- [fence_vmware_rest — referência de implementação](https://github.com/ClusterLabs/fence-agents/blob/main/agents/vmware_rest/fence_vmware_rest.py)
- [Pacemaker — Clusters from Scratch](https://clusterlabs.org/projects/pacemaker/doc/3.0/Clusters_from_Scratch/singlehtml/)
- [Pacemaker Administration](https://clusterlabs.org/projects/pacemaker/doc/3.0/Pacemaker_Administration/singlehtml/)
- [Pacemaker Explained](https://clusterlabs.org/projects/pacemaker/doc/3.0/Pacemaker_Explained/singlehtml/)
- [Magalu Cloud API](https://magalu.cloud)
