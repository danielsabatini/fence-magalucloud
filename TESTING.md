# Testes — fence_magalucloud

Testes organizados em três fases progressivas. Execute sempre em ordem.

| Fase | Ambiente | Pré-requisito |
|---|---|---|
| [Fase 1](#fase-1--testes-locais-uv-run) | Local (desenvolvimento) | `.env` com `API_KEY`, `REGION`, `VM_ID` |
| [Fase 2](#fase-2--testes-no-cluster-sem-pacemaker) | Nós do cluster | [INSTALL.md](INSTALL.md) passos 0–13 concluídos |
| [Fase 3](#fase-3--integração-com-o-pacemaker) | Cluster com Pacemaker | [INSTALL.md](INSTALL.md) completo (passos 0–16) |

---

## Fase 1 — Testes locais (`uv run`)

**Pré-requisito:**

```bash
source .env
# Variáveis necessárias: API_KEY, REGION, VM_ID
```

---

### 1.1 Sanidade

Valida que o agente inicializa, exibe ajuda, gera metadados XML e conecta à API.

```bash
# Help do agente
uv run fence-magalucloud --help
```

```bash
# Metadados XML (o que o Pacemaker lerá com -o metadata)
uv run fence-magalucloud -o metadata
```

```bash
# Monitor: valida conectividade com a API (requer chave válida)
uv run fence-magalucloud \
    --api-key=$API_KEY --region=$REGION -o monitor
echo "exit esperado: 0 | obtido: $?"
```

---

### 1.2 Autenticação

Valida que chaves inválidas retornam EC_LOGIN_DENIED (exit 3) e chaves válidas retornam EC_OK (exit 0).

> A API do Magalu Cloud retorna HTTP 403 (não 401) para chaves inválidas.

```bash
# Chave inválida → EC_LOGIN_DENIED (exit 3)
uv run fence-magalucloud \
    --api-key=chave-invalida --region=$REGION \
    --plug=$VM_ID -o status
echo "exit esperado: 3 | obtido: $?"
```

```bash
# Chave válida → EC_OK (exit 0)
uv run fence-magalucloud \
    --api-key=$API_KEY --region=$REGION \
    --plug=$VM_ID -o status
echo "exit esperado: 0 | obtido: $?"
```

---

### 1.3 Status e listagem

Valida leitura do estado de uma VM e listagem de todas as instâncias da região.

```bash
# Status de uma VM específica
uv run fence-magalucloud \
    --api-key=$API_KEY --region=$REGION \
    --plug=$VM_ID -o status
```

```bash
# Listar todas as instâncias da região
uv run fence-magalucloud \
    --api-key=$API_KEY --region=$REGION \
    -o list
```

---

### 1.4 Ações de energia

Valida os ciclos de desligamento, ligamento e reboot.

```bash
# Desligar
uv run fence-magalucloud \
    --api-key=$API_KEY --region=$REGION --plug=$VM_ID -o off
echo "exit esperado: 0 | obtido: $?"
```

```bash
# Confirmar estado
uv run fence-magalucloud \
    --api-key=$API_KEY --region=$REGION --plug=$VM_ID -o status
```

```bash
# Ligar
uv run fence-magalucloud \
    --api-key=$API_KEY --region=$REGION --plug=$VM_ID -o on
echo "exit esperado: 0 | obtido: $?"
```

```bash
# Reboot (off + on sequencial via fencing)
uv run fence-magalucloud \
    --api-key=$API_KEY --region=$REGION --plug=$VM_ID -o reboot
echo "exit esperado: 0 | obtido: $?"
```

---

### 1.5 Modo stdin

Valida o modo de entrada que o Pacemaker usa em produção (parâmetros via stdin).

```bash
# Status via stdin
printf "api_key=$API_KEY\nregion=$REGION\nplug=$VM_ID\naction=status\n" \
    | uv run fence-magalucloud
echo "exit esperado: 0 | obtido: $?"
```

```bash
# List via stdin com verbose
printf "api_key=$API_KEY\nregion=$REGION\naction=list\nverbose=1\n" \
    | uv run fence-magalucloud
```

```bash
# Off via stdin
printf "api_key=$API_KEY\nregion=$REGION\nplug=$VM_ID\naction=off\n" \
    | uv run fence-magalucloud
echo "exit esperado: 0 | obtido: $?"
```

---

### 1.6 Cenários de erro

Valida os exit codes corretos para cada tipo de falha.

| Cenário | Exit esperado |
|---------|--------------|
| VM inexistente | 8 (EC_STATUS) |
| Região inválida | 8 (EC_STATUS) |
| `--plug` ausente | 1 (lib fencing) |
| `--api-key` ausente | 2 (EC_BAD_ARGS) |

```bash
# VM inexistente → EC_STATUS (exit 8)
uv run fence-magalucloud \
    --api-key=$API_KEY --region=$REGION \
    --plug=00000000-0000-0000-0000-000000000000 -o status
echo "exit esperado: 8 | obtido: $?"
```

```bash
# Região inválida → EC_STATUS (exit 8)
uv run fence-magalucloud \
    --api-key=$API_KEY --region=regiao-invalida --plug=$VM_ID -o status
echo "exit esperado: 8 | obtido: $?"
```

```bash
# --plug ausente → exit 1 (comportamento da lib fencing, não controlamos)
uv run fence-magalucloud \
    --api-key=$API_KEY --region=$REGION -o status
echo "exit esperado: 1 | obtido: $?"
```

```bash
# --api-key ausente → EC_BAD_ARGS (exit 2)
uv run fence-magalucloud --region=$REGION --plug=$VM_ID -o status
echo "exit esperado: 2 | obtido: $?"
```

---

## Fase 2 — Testes no cluster (sem Pacemaker)

**Pré-requisito:** [INSTALL.md](INSTALL.md) passos 0–13 concluídos em ambos os nós.
As variáveis de ambiente já estão definidas via `/etc/profile.d/fence-magalucloud.sh`.

Execute os testes a partir de **cada nó**, usando o VM_ID do nó **oposto** como `--plug`
(é o nó que será fenceado):

- No nó 1: testa fencear o nó 2 → usa `$VM_ID_NODE2`
- No nó 2: testa fencear o nó 1 → usa `$VM_ID_NODE1`

---

### 2.1 Conectar no nó 1 e configurar VM_ID

```bash
ssh -i ~/.ssh/<chave.pem> <usuario>@$IP_NODE1
```

```bash
# Do nó 1, fenceamos o nó 2
export VM_ID=$VM_ID_NODE2
```

### 2.2 Sanidade

```bash
# Help do agente
/usr/sbin/fence_magalucloud --help
```

```bash
# Metadados XML
/usr/sbin/fence_magalucloud -o metadata
```

```bash
# Monitor: valida conectividade com a API
/usr/sbin/fence_magalucloud \
    --api-key=$API_KEY --region=$REGION -o monitor
echo "exit esperado: 0 | obtido: $?"
```

---

### 2.3 Autenticação

```bash
# Chave inválida → EC_LOGIN_DENIED (exit 3)
/usr/sbin/fence_magalucloud \
    --api-key=chave-invalida --region=$REGION \
    --plug=$VM_ID -o status
echo "exit esperado: 3 | obtido: $?"
```

```bash
# Chave válida → EC_OK (exit 0)
/usr/sbin/fence_magalucloud \
    --api-key=$API_KEY --region=$REGION \
    --plug=$VM_ID -o status
echo "exit esperado: 0 | obtido: $?"
```

---

### 2.4 Status e listagem

```bash
# Status de uma VM específica
/usr/sbin/fence_magalucloud \
    --api-key=$API_KEY --region=$REGION \
    --plug=$VM_ID -o status
```

```bash
# Listar todas as instâncias da região
/usr/sbin/fence_magalucloud \
    --api-key=$API_KEY --region=$REGION \
    -o list
```

---

### 2.5 Ações de energia

```bash
# Desligar
/usr/sbin/fence_magalucloud \
    --api-key=$API_KEY --region=$REGION --plug=$VM_ID -o off
echo "exit esperado: 0 | obtido: $?"
```

```bash
# Confirmar estado
/usr/sbin/fence_magalucloud \
    --api-key=$API_KEY --region=$REGION --plug=$VM_ID -o status
```

```bash
# Ligar
/usr/sbin/fence_magalucloud \
    --api-key=$API_KEY --region=$REGION --plug=$VM_ID -o on
echo "exit esperado: 0 | obtido: $?"
```

```bash
# Reboot (off + on sequencial via fencing)
/usr/sbin/fence_magalucloud \
    --api-key=$API_KEY --region=$REGION --plug=$VM_ID -o reboot
echo "exit esperado: 0 | obtido: $?"
```

---

### 2.6 Modo stdin

```bash
# Status via stdin
printf "api_key=$API_KEY\nregion=$REGION\nplug=$VM_ID\naction=status\n" \
    | /usr/sbin/fence_magalucloud
echo "exit esperado: 0 | obtido: $?"
```

```bash
# List via stdin com verbose
printf "api_key=$API_KEY\nregion=$REGION\naction=list\nverbose=1\n" \
    | /usr/sbin/fence_magalucloud
```

```bash
# Off via stdin
printf "api_key=$API_KEY\nregion=$REGION\nplug=$VM_ID\naction=off\n" \
    | /usr/sbin/fence_magalucloud
echo "exit esperado: 0 | obtido: $?"
```

---

### 2.7 Cenários de erro

```bash
# VM inexistente → EC_STATUS (exit 8)
/usr/sbin/fence_magalucloud \
    --api-key=$API_KEY --region=$REGION \
    --plug=00000000-0000-0000-0000-000000000000 -o status
echo "exit esperado: 8 | obtido: $?"
```

```bash
# Região inválida → EC_STATUS (exit 8)
/usr/sbin/fence_magalucloud \
    --api-key=$API_KEY --region=regiao-invalida --plug=$VM_ID -o status
echo "exit esperado: 8 | obtido: $?"
```

```bash
# --plug ausente → exit 1 (comportamento da lib fencing)
/usr/sbin/fence_magalucloud \
    --api-key=$API_KEY --region=$REGION -o status
echo "exit esperado: 1 | obtido: $?"
```

```bash
# --api-key ausente → EC_BAD_ARGS (exit 2)
/usr/sbin/fence_magalucloud --region=$REGION --plug=$VM_ID -o status
echo "exit esperado: 2 | obtido: $?"
```

---

### 2.8 Repetir no nó 2

```bash
ssh -i ~/.ssh/<chave.pem> <usuario>@$IP_NODE2
```

```bash
# Do nó 2, fenceamos o nó 1
export VM_ID=$VM_ID_NODE1
```

Execute os testes de 2.2 até 2.7.

---

## Fase 3 — Integração com o Pacemaker

**Pré-requisito:** [INSTALL.md](INSTALL.md) completo (passos 0–16). Executar no nó primário do cluster.
As variáveis de ambiente já estão definidas via `/etc/profile.d/fence-magalucloud.sh`.

> **Atenção:** o teste 3.4 causa desligamento real do nó alvo. Confirme antes de executar.

> **Topologia:** cada agente STONITH deve rodar no nó **oposto** ao que ele fenceia.
> `fence-node1` (fenceia node1) deve rodar em node2, e `fence-node2` (fenceia node2) deve
> rodar em node1. Um nó não pode fencear a si mesmo.

---

### 3.1 Validar metadados via Pacemaker

Executar em **node1**:

```bash
# Pacemaker consulta -o metadata internamente ao descrever o agente
sudo pcs stonith describe fence_magalucloud
```

Saída esperada:

```
fence_magalucloud - Fence agent para instâncias de VM no Magalu Cloud

fence_magalucloud é um fence agent que interage com a API REST do Magalu Cloud para gerenciar o estado de energia de
instâncias de máquinas virtuais. Suporta as ações: on, off, reboot, status e list.

Stonith options:
  api_key (required)
    Description: Chave de API do Magalu Cloud
    Type: string
  plug
    Description: Physical plug number on device, UUID or identification of machine
    Type: string
  region
    Description: Região do Magalu Cloud
    Type: string
    Default: br-se1
  ...
Default operations:
  monitor:
    interval=60s
```

---

### 3.2 Status do stonith no cluster

Executar em **node1**:

```bash
# Status geral do cluster
sudo pcs status
```

Saída esperada: ambos os nós online, cada recurso rodando no nó oposto:

```
Full List of Resources:
  * fence-node1  (stonith:fence_magalucloud):  Started $HOSTNAME_NODE2
  * fence-node2  (stonith:fence_magalucloud):  Started $HOSTNAME_NODE1
```

```bash
# Configuração dos recursos stonith
sudo pcs stonith config
```

Saída esperada: configuração dos dois recursos `fence-node1` e `fence-node2` conforme
[INSTALL.md](INSTALL.md) passo 14.

---

### 3.3 Teste de fencing via Pacemaker

> **Atenção:** estes comandos causam desligamento real do nó alvo. Confirme antes de executar.

> **Topologia do teste:**
> - `fence-node2` roda em **node1** → node1 fenceia node2
> - `fence-node1` roda em **node2** → node2 fenceia node1

#### 3.3.1 node1 fenceia node2

Executar em **node1**:

```bash
# Verificar que ambos os nós estão online e sem falhas antes de fencear
sudo pcs status
```

Saída esperada: ambos online, `fence-node2 Started $HOSTNAME_NODE1`, sem `Failed Resource Actions`:

```
Node List:
  * Online: [ $HOSTNAME_NODE1 $HOSTNAME_NODE2 ]
Full List of Resources:
  * fence-node1  (stonith:fence_magalucloud):  Started $HOSTNAME_NODE2
  * fence-node2  (stonith:fence_magalucloud):  Started $HOSTNAME_NODE1
```

```bash
sudo pcs stonith fence $HOSTNAME_NODE2
echo "exit esperado: 0 | obtido: $?"
```

Saída esperada: `Node $HOSTNAME_NODE2 fenced`

```bash
# Verificar logs do fencing
sudo grep fence /var/log/syslog | tail -20
```

Linhas-chave a confirmar no log — todas devem estar presentes:

```
pacemaker-fenced: notice: Client stonith_admin wants to fence (reboot) $HOSTNAME_NODE2 using any device
pacemaker-fenced: notice: Requesting that $HOSTNAME_NODE1 perform 'reboot' action targeting $HOSTNAME_NODE2
pacemaker-fenced: notice: Node $HOSTNAME_NODE2 state is now lost
pacemaker-fenced: notice: Operation 'reboot' targeting $HOSTNAME_NODE2 using fence-node2 returned 0
pacemaker-fenced: notice: Operation 'reboot' targeting $HOSTNAME_NODE2 by $HOSTNAME_NODE1 for stonith_admin: OK (complete)
pacemaker-fenced: notice: Node $HOSTNAME_NODE2 state is now member
```

```bash
# Verificar o status dos nós (aguardar node2 reiniciar e voltar)
sudo pcs status nodes
```

Saída esperada: após o reboot, node2 volta automaticamente ao cluster:

```
Pacemaker Nodes:
 Online: $HOSTNAME_NODE1 $HOSTNAME_NODE2
 Standby:
 Offline:
```

> O `pcs stonith fence` executa reboot por padrão. O nó alvo é desligado, reinicia e
> reingressa no cluster automaticamente — esse é o comportamento correto do STONITH.

---

#### 3.3.2 node2 fenceia node1

> **Pré-requisito:** aguardar node2 estar `Online` antes de executar.
> Se `pcs status` exibir `Failed Fencing Actions` de tentativas anteriores, limpar antes:
> ```bash
> sudo pcs stonith history cleanup
> ```

Executar em **node2**:

```bash
# Verificar que ambos os nós estão online e sem falhas antes de fencear
sudo pcs status
```

Saída esperada: ambos online, `fence-node1 Started $HOSTNAME_NODE2`, sem `Failed Resource Actions`:

```
Node List:
  * Online: [ $HOSTNAME_NODE1 $HOSTNAME_NODE2 ]
Full List of Resources:
  * fence-node1  (stonith:fence_magalucloud):  Started $HOSTNAME_NODE2
  * fence-node2  (stonith:fence_magalucloud):  Started $HOSTNAME_NODE1
```

```bash
sudo pcs stonith fence $HOSTNAME_NODE1
echo "exit esperado: 0 | obtido: $?"
```

Saída esperada: `Node $HOSTNAME_NODE1 fenced`

```bash
# Verificar logs do fencing
sudo grep fence /var/log/syslog | tail -20
```

Linhas-chave a confirmar no log — todas devem estar presentes:

```
pacemaker-fenced: notice: Client stonith_admin wants to fence (reboot) $HOSTNAME_NODE1 using any device
pacemaker-fenced: notice: Requesting that $HOSTNAME_NODE2 perform 'reboot' action targeting $HOSTNAME_NODE1
pacemaker-fenced: notice: Node $HOSTNAME_NODE1 state is now lost
pacemaker-fenced: notice: Operation 'reboot' targeting $HOSTNAME_NODE1 using fence-node1 returned 0
pacemaker-fenced: notice: Operation 'reboot' targeting $HOSTNAME_NODE1 by $HOSTNAME_NODE2 for stonith_admin: OK (complete)
pacemaker-fenced: notice: Node $HOSTNAME_NODE1 state is now member
```

```bash
# Verificar o status dos nós (aguardar node1 reiniciar e voltar)
sudo pcs status nodes
```

Saída esperada: após o reboot, node1 volta automaticamente ao cluster:

```
Pacemaker Nodes:
 Online: $HOSTNAME_NODE1 $HOSTNAME_NODE2
 Standby:
 Offline:
```

---

### 3.4 Restaurar o nó após fencing com `--off`

> Esta seção só se aplica se o fencing foi executado com `--off` (desligamento permanente).
> No teste padrão (3.3), o Pacemaker usa reboot e o nó volta ao cluster automaticamente —
> nenhuma ação manual é necessária.

Caso tenha executado `pcs stonith fence <nó> --off`, restaurar manualmente:

```bash
# Ligar a VM via fence agent (exemplo: restaurar node2)
/usr/sbin/fence_magalucloud \
    --api-key=$API_KEY --region=$REGION --plug=$VM_ID_NODE2 -o on
echo "exit esperado: 0 | obtido: $?"
```

```bash
# Reintegrar o nó ao cluster
sudo pcs cluster start $HOSTNAME_NODE2
```

Saída esperada: `Starting Cluster...`

```bash
# Confirmar que o nó voltou ao cluster
sudo pcs status nodes
```

Saída esperada: nó listado como `Online`.
