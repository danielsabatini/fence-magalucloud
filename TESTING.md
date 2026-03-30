# Guia de Testes — fence_magalucloud

Testes organizados em três fases progressivas. Execute sempre em ordem.

**Pré-requisito comum a todas as fases:**

```bash
source .env
# Variáveis necessárias: API_KEY, REGION, VM_ID
```

---
## Fase 1 — Testes locais (`uv run`)

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

## Fase 2 — Testes no servidor do cluster (sem Pacemaker)

Os comandos de instalação são executados **dentro de cada nó** via SSH.
O `make install` instala as dependências e copia os arquivos para `/usr/sbin/` automaticamente.

---

### Instalação em cls1

```bash
# Substitua <usuario>, <chave.pem> e <ip-ou-hostname> pelos valores reais
ssh -i ~/.ssh/<chave.pem> <usuario>@<ip-ou-hostname-cls1>
```

Dentro de cls1:

```bash
# Instalar git e make se necessário
sudo apt install -y git make
```

```bash
# Instalar fence-agents-common (provê o módulo fencing e suas dependências)
sudo apt install -y fence-agents-common
```

```bash
git clone https://github.com/danielsabatini/fence-magalucloud.git
```

```bash
cd fence-magalucloud
```

```bash
make install
```

Saída esperada:
```
==> Instalando dependências do sistema...
==> Instalando arquivos em /usr/sbin...
==> Instalação concluída.
    Agente: /usr/sbin/fence_magalucloud
    Lib:    /usr/sbin/fencing.py
```

---

### Instalação em cls2

```bash
# Substitua <usuario>, <chave.pem> e <ip-ou-hostname> pelos valores reais
ssh -i ~/.ssh/<chave.pem> <usuario>@<ip-ou-hostname-cls2>
```

Dentro de cls2:

```bash
# Instalar git e make se necessário
sudo apt install -y git make
```

```bash
# Instalar fence-agents-common (provê o módulo fencing e suas dependências)
sudo apt install -y fence-agents-common
```

```bash
git clone https://github.com/danielsabatini/fence-magalucloud.git
```

```bash
cd fence-magalucloud
```

```bash
make install
```

Saída esperada:
```
==> Instalando dependências do sistema...
==> Instalando arquivos em /usr/sbin...
==> Instalação concluída.
    Agente: /usr/sbin/fence_magalucloud
    Lib:    /usr/sbin/fencing.py
```

---

> **Atualizar** o agente após uma nova versão no repositório (executar dentro do diretório clonado):
> ```bash
> cd fence-magalucloud
> ```
> ```bash
> make update
> ```

> **Remover** o agente do nó (executar dentro do diretório clonado):
> ```bash
> cd fence-magalucloud
> ```
> ```bash
> make uninstall
> ```
---


### 2.1. Conectar no nó 1 do cluster
```bash
# Substitua <usuario>, <chave.pem> e <ip-ou-hostname> pelos valores reais
ssh -i ~/.ssh/<chave.pem> <usuario>@<ip-ou-hostname-cls1>
```

```bash
# Definir variáveis nó 1 (CLS1)
export API_KEY='50302b80-fc24-499e-b76f-c022df924a60'
export REGION='br-ne1'
# Incluir o ID da VM do nó 2 (CLS2)
export VM_ID='07dfa2fa-c483-470e-9cb5-423697f522fd'
```

### 2.2. Sanidade
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

### 2.3. Autenticação

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

### 2.4. Status e listagem

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

### 2.5. Ações de energia

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

### 2.6. Modo stdin

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

### 2.7. Cenários de erro

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

### 2.8. Conectar no nó 2 do cluster
```bash
# Substitua <usuario>, <chave.pem> e <ip-ou-hostname> pelos valores reais
ssh -i ~/.ssh/<chave.pem> <usuario>@<ip-ou-hostname-cls2>
```

```bash
# Definir variáveis (CLS2)
export API_KEY='50302b80-fc24-499e-b76f-c022df924a60'
export REGION='br-ne1'
# Incluir o ID da VM do nó 1 (CLS1)
export VM_ID='12247f87-734a-4722-bd39-14dd5342f1b1'
```
**Executar os testes de 2.2 até 2.7.**

## Fase 3 — Integração com o Pacemaker

**Pré-requisito:** Fase 2 concluída em todos os nós. Executar no nó primário do cluster (cls1).

> **Atenção:** o teste 3.4 causa desligamento real do nó alvo. Confirme antes de executar.

> **Topologia:** cada agente STONITH deve rodar no nó **oposto** ao que ele fenceia.
> `fence-cls1` (fenceia cls1) deve rodar em cls2, e `fence-cls2` (fenceia cls2) deve rodar em cls1.
> Um nó não pode fencear a si mesmo.

---

### 3.1 Instalar os recursos stonith

Executar em **cls1**:

```bash
# Definir variáveis
export API_KEY='50302b80-fc24-499e-b76f-c022df924a60'
export REGION='br-ne1'
export VM_ID_CLS1='<VM_ID de cls1>'
export VM_ID_CLS2='<VM_ID de cls2>'
```

```bash
# Criar recurso que fenceia cls1 (será executado por cls2)
sudo pcs stonith create fence-cls1 fence_magalucloud \
    api_key="$API_KEY" \
    region="$REGION" \
    plug="$VM_ID_CLS1" \
    op monitor interval=60s
```

Saída esperada: nenhuma (sem erros = sucesso).

```bash
# Restringir fence-cls1 para rodar apenas em cls2
sudo pcs constraint location fence-cls1 avoids cls1
```

Saída esperada: nenhuma (sem erros = sucesso).

```bash
# Criar recurso que fenceia cls2 (será executado por cls1)
sudo pcs stonith create fence-cls2 fence_magalucloud \
    api_key="$API_KEY" \
    region="$REGION" \
    plug="$VM_ID_CLS2" \
    op monitor interval=60s
```

Saída esperada: nenhuma (sem erros = sucesso).

```bash
# Restringir fence-cls2 para rodar apenas em cls1
sudo pcs constraint location fence-cls2 avoids cls2
```

Saída esperada: nenhuma (sem erros = sucesso).

```bash
# Verificar os recursos criados
sudo pcs stonith config
```

Saída esperada:
```
Resource: fence-cls1 (class=stonith type=fence_magalucloud)
  Attributes: fence-cls1-instance_attributes
    api_key=<API_KEY>
    plug=<VM_ID_CLS1>
    region=br-ne1
  Operations:
    monitor: fence-cls1-monitor-interval-60s
      interval=60s
Resource: fence-cls2 (class=stonith type=fence_magalucloud)
  Attributes: fence-cls2-instance_attributes
    api_key=<API_KEY>
    plug=<VM_ID_CLS2>
    region=br-ne1
  Operations:
    monitor: fence-cls2-monitor-interval-60s
      interval=60s
```

---

### 3.2 Validar metadados via Pacemaker

Executar em **cls1**:

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

### 3.3 Status do stonith no cluster

Executar em **cls1**:

```bash
# Status geral do cluster
sudo pcs status
```

Saída esperada: ambos os nós online, cada recurso rodando no nó oposto:
```
Full List of Resources:
  * fence-cls1	(stonith:fence_magalucloud):	 Started cls2
  * fence-cls2	(stonith:fence_magalucloud):	 Started cls1
```

```bash
# Configuração dos recursos stonith
sudo pcs stonith config
```

Saída esperada: configuração dos dois recursos `fence-cls1` e `fence-cls2` conforme 3.1.

---

### 3.4 Teste de fencing via Pacemaker

> **Atenção:** estes comandos causam desligamento real do nó alvo. Confirme antes de executar.

> **Topologia do teste:**
> - `fence-cls2` roda em **cls1** → cls1 fenceia cls2
> - `fence-cls1` roda em **cls2** → cls2 fenceia cls1

#### 3.4.1 cls1 fenceia cls2

Executar em **cls1**:

```bash
# Verificar que ambos os nós estão online e sem falhas antes de fencear
sudo pcs status
```

Saída esperada: ambos online, `fence-cls2 Started cls1`, sem `Failed Resource Actions`:
```
Node List:
  * Online: [ cls1 cls2 ]
Full List of Resources:
  * fence-cls1	(stonith:fence_magalucloud):	 Started cls2
  * fence-cls2	(stonith:fence_magalucloud):	 Started cls1
```

```bash
sudo pcs stonith fence cls2
echo "exit esperado: 0 | obtido: $?"
```

Saída esperada: `Node cls2 fenced`

```bash
# Verificar logs do fencing (executar em cls1)
sudo grep fence /var/log/syslog | tail -20
```

Linhas-chave a confirmar no log — todas devem estar presentes:
```
pacemaker-fenced: notice: Client stonith_admin wants to fence (reboot) cls2 using any device
pacemaker-fenced: notice: Requesting that cls1 perform 'reboot' action targeting cls2
pacemaker-fenced: notice: Node cls2 state is now lost
pacemaker-fenced: notice: Operation 'reboot' targeting cls2 using fence-cls2 returned 0
pacemaker-fenced: notice: Operation 'reboot' targeting cls2 by cls1 for stonith_admin: OK (complete)
pacemaker-fenced: notice: Node cls2 state is now member
```

```bash
# Verificar o status dos nós (aguardar cls2 reiniciar e voltar)
sudo pcs status nodes
```

Saída esperada: após o reboot, cls2 volta automaticamente ao cluster:
```
Pacemaker Nodes:
 Online: cls1 cls2
 Standby:
 Offline:
```

> O `pcs stonith fence` executa reboot por padrão. O nó alvo é desligado, reinicia e
> reingressa no cluster automaticamente — esse é o comportamento correto do STONITH.

---

#### 3.4.2 cls2 fenceia cls1

> **Pré-requisito:** aguardar cls2 estar `Online` antes de executar.
> Se `pcs status` exibir `Failed Fencing Actions` de tentativas anteriores, limpar antes:
> ```bash
> sudo pcs stonith history cleanup
> ```

Executar em **cls2**:

```bash
# Verificar que ambos os nós estão online e sem falhas antes de fencear
sudo pcs status
```

Saída esperada: ambos online, `fence-cls1 Started cls2`, sem `Failed Resource Actions`:
```
Node List:
  * Online: [ cls1 cls2 ]
Full List of Resources:
  * fence-cls1	(stonith:fence_magalucloud):	 Started cls2
  * fence-cls2	(stonith:fence_magalucloud):	 Started cls1
```

```bash
sudo pcs stonith fence cls1
echo "exit esperado: 0 | obtido: $?"
```

Saída esperada: `Node cls1 fenced`

```bash
# Verificar logs do fencing (executar em cls2)
sudo grep fence /var/log/syslog | tail -20
```

Linhas-chave a confirmar no log — todas devem estar presentes:
```
pacemaker-fenced: notice: Client stonith_admin wants to fence (reboot) cls1 using any device
pacemaker-fenced: notice: Requesting that cls2 perform 'reboot' action targeting cls1
pacemaker-fenced: notice: Node cls1 state is now lost
pacemaker-fenced: notice: Operation 'reboot' targeting cls1 using fence-cls1 returned 0
pacemaker-fenced: notice: Operation 'reboot' targeting cls1 by cls2 for stonith_admin: OK (complete)
pacemaker-fenced: notice: Node cls1 state is now member
```

```bash
# Verificar o status dos nós (aguardar cls1 reiniciar e voltar)
sudo pcs status nodes
```

Saída esperada: após o reboot, cls1 volta automaticamente ao cluster:
```
Pacemaker Nodes:
 Online: cls1 cls2
 Standby:
 Offline:
```

---

### 3.5 Restaurar o nó após fencing com `--off`

> Esta seção só se aplica se o fencing foi executado com `--off` (desligamento permanente).
> No teste padrão (3.4), o Pacemaker usa reboot e o nó volta ao cluster automaticamente — nenhuma ação manual é necessária.

Caso tenha executado `pcs stonith fence <nó> --off`, restaurar manualmente:

```bash
# Ligar a VM via fence agent (substitua VM_ID e nó conforme o caso)
/usr/sbin/fence_magalucloud \
    --api-key=$API_KEY --region=$REGION --plug=$VM_ID_CLS2 -o on
echo "exit esperado: 0 | obtido: $?"
```

```bash
# Reintegrar o nó ao cluster
sudo pcs cluster start cls2
```

Saída esperada: `Starting Cluster...`

```bash
# Confirmar que o nó voltou ao cluster
sudo pcs status nodes
```

Saída esperada: nó listado como `Online`.
