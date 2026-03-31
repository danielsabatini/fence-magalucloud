# Instalação — fence_magalucloud

Guia completo para configurar um cluster Pacemaker de dois nós (Ubuntu 24.04) e instalar
o `fence_magalucloud` como device STONITH.

Após a instalação, consulte [TESTING.md](TESTING.md) para validar o agente.

---

## Topologia de referência

| Nó | Hostname | IP |
|---|---|---|
| Nó 1 | `$HOSTNAME_NODE1` | `$IP_NODE1` |
| Nó 2 | `$HOSTNAME_NODE2` | `$IP_NODE2` |

---

## 0. Definir variáveis de ambiente

Execute em **ambos os nós** antes de qualquer outro passo. Preencha com os valores reais do
seu ambiente:

```bash
sudo tee /etc/profile.d/fence-magalucloud.sh << 'EOF'
export API_KEY='<sua-api-key>'
export REGION='<regiao>'
export HOSTNAME_NODE1='<hostname-node1>'
export HOSTNAME_NODE2='<hostname-node2>'
export IP_NODE1='<ip-node1>'
export IP_NODE2='<ip-node2>'
export VM_ID_NODE1='<vm-id-node1>'
export VM_ID_NODE2='<vm-id-node2>'
EOF
```

```bash
source /etc/profile.d/fence-magalucloud.sh
```

> O arquivo `/etc/profile.d/fence-magalucloud.sh` é carregado automaticamente em todo login
> — as variáveis persistem após reboot sem necessidade de `export` manual.

---

## 1. Hardening inicial — evitar auto-start de serviços

Execute em **ambos os nós** antes de instalar qualquer pacote:

```bash
sudo systemctl mask corosync
sudo systemctl mask pacemaker
```

Garante que nenhum serviço sobe automaticamente durante a instalação, evitando cluster
parcial ou estado inconsistente.

---

## 2. Instalação de pacotes

Execute em **ambos os nós**:

```bash
sudo apt update
sudo apt upgrade -y

sudo apt install -y \
  pacemaker \
  pcs \
  corosync \
  nodejs \
  npm \
  autoconf \
  automake \
  pkgconf \
  git \
  make \
  cockpit \
  python3-requests \
  fence-agents-common
```

---

## 3. Configuração base

### Hostname

```bash
sudo hostnamectl set-hostname $HOSTNAME_NODE1   # executar no nó 1
sudo hostnamectl set-hostname $HOSTNAME_NODE2   # executar no nó 2
```

### /etc/hosts (obrigatório em ambos os nós)

```bash
# Adicionar entradas dos nós
sudo tee -a /etc/hosts << EOF
$IP_NODE1  $HOSTNAME_NODE1
$IP_NODE2  $HOSTNAME_NODE2
EOF
```

```bash
# Remover linha 127.0.1.1 se existir (causa resolução incorreta de hostname)
sudo sed -i '/^127\.0\.1\.1/d' /etc/hosts
```

### Validação

```bash
getent hosts $HOSTNAME_NODE1
getent hosts $HOSTNAME_NODE2
```

---

## 4. Usuário hacluster

Execute em **ambos os nós** com a **mesma senha**:

```bash
sudo passwd hacluster
```

---

## 5. Habilitar e iniciar o pcsd

Execute em **ambos os nós**:

```bash
sudo systemctl enable pcsd
sudo systemctl start pcsd
```

### Validação crítica

```bash
curl -k https://localhost:2224
```

Saída esperada:

```
401 Unauthorized
```

```bash
sudo ss -tnlp4
```

Saída esperada (porta 2224 em LISTEN):

```
State    Recv-Q   Send-Q      Local Address:Port       Peer Address:Port   Process
LISTEN   0        4096        127.0.0.53%lo:53              0.0.0.0:*       users:(("systemd-resolve",...))
LISTEN   0        4096              0.0.0.0:5355            0.0.0.0:*       users:(("systemd-resolve",...))
LISTEN   0        4096           127.0.0.54:53              0.0.0.0:*       users:(("systemd-resolve",...))
LISTEN   0        128               0.0.0.0:22              0.0.0.0:*       users:(("sshd",...))
LISTEN   0        128               0.0.0.0:2224            0.0.0.0:*       users:(("pcsd",...))
```

---

## 6. Liberar serviços para o cluster

Execute em **ambos os nós** após confirmar que o `pcsd` está saudável:

```bash
sudo systemctl unmask corosync
sudo systemctl unmask pacemaker
```

---

## 7. Autenticação dos nós

Execute **apenas no nó 1**:

```bash
sudo pcs host auth \
  $HOSTNAME_NODE1 addr=$IP_NODE1 \
  $HOSTNAME_NODE2 addr=$IP_NODE2 \
  -u hacluster -p <senha-hacluster>
```

> O parâmetro `addr=` é obrigatório. Sem ele, o pcs não armazena os endereços em
> `known-hosts` e o `pcs cluster setup` falhará com "Hosts not known to pcs".

### Validação

```bash
sudo ls /var/lib/pcsd/
```

Saída esperada:

```
known-hosts  tokens
```

---

## 8. Garantir estado limpo

Execute em **ambos os nós**:

```bash
sudo systemctl stop corosync
sudo systemctl stop pacemaker
```

Limpeza completa (execute em qualquer nó):

```bash
sudo pcs cluster destroy
sudo rm -rf /etc/corosync/*
sudo rm -rf /var/lib/pacemaker/*
sudo rm -rf /var/lib/corosync/*
```

---

## 9. Criar o cluster

Execute **apenas no nó 1**:

```bash
sudo pcs cluster setup mycluster \
  $HOSTNAME_NODE1 addr=$IP_NODE1 \
  $HOSTNAME_NODE2 addr=$IP_NODE2
```

---

## 10. Iniciar o cluster

```bash
sudo pcs cluster start --all
```

---

## 11. Habilitar início automático

```bash
sudo pcs cluster enable --all
```

---

## 12. Validação do cluster

```bash
sudo pcs status
```

Saída esperada:

```
Cluster name: mycluster
Status of pacemakerd: 'Pacemaker is running' (last updated ...)
Cluster Summary:
  * Stack: corosync (Pacemaker is running)
  * Current DC: $HOSTNAME_NODE1 ...
  * 2 nodes configured, 0 resource instances configured

Node List:
  * Online: [ $HOSTNAME_NODE1 $HOSTNAME_NODE2 ]
```

---

## 13. Instalar o fence_magalucloud em cada nó

### Instalação em node1

```bash
ssh -i ~/.ssh/<chave.pem> <usuario>@$IP_NODE1
```

```bash
sudo apt install -y git make fence-agents-common
```

```bash
git clone https://github.com/danielsabatini/fence-magalucloud.git
cd fence-magalucloud
sudo make install
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

### Instalação em node2

```bash
ssh -i ~/.ssh/<chave.pem> <usuario>@$IP_NODE2
```

```bash
sudo apt install -y git make fence-agents-common
```

```bash
git clone https://github.com/danielsabatini/fence-magalucloud.git
cd fence-magalucloud
sudo make install
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

> **Atualizar** o agente após uma nova versão:
> ```bash
> cd fence-magalucloud && make update
> ```

> **Remover** o agente do nó:
> ```bash
> cd fence-magalucloud && make uninstall
> ```

---

## 14. Criar o recurso de fencing

> **Topologia:** cada agente STONITH deve rodar no nó **oposto** ao que ele fenceia.
> `fence-node1` (fenceia node1) deve rodar em node2, e `fence-node2` (fenceia node2) deve
> rodar em node1. Um nó não pode fencear a si mesmo.

Execute **apenas no nó 1**:

```bash
# Criar recurso que fenceia node1 (será executado por node2)
sudo pcs stonith create fence-node1 fence_magalucloud \
    api_key="$API_KEY" \
    region="$REGION" \
    plug="$VM_ID_NODE1" \
    op monitor interval=60s
```

Saída esperada: nenhuma (sem erros = sucesso).

```bash
# Restringir fence-node1 para rodar apenas em node2
sudo pcs constraint location fence-node1 avoids $HOSTNAME_NODE1
```

Saída esperada: nenhuma (sem erros = sucesso).

```bash
# Criar recurso que fenceia node2 (será executado por node1)
sudo pcs stonith create fence-node2 fence_magalucloud \
    api_key="$API_KEY" \
    region="$REGION" \
    plug="$VM_ID_NODE2" \
    op monitor interval=60s
```

Saída esperada: nenhuma (sem erros = sucesso).

```bash
# Restringir fence-node2 para rodar apenas em node1
sudo pcs constraint location fence-node2 avoids $HOSTNAME_NODE2
```

Saída esperada: nenhuma (sem erros = sucesso).

```bash
# Verificar os recursos criados
sudo pcs stonith config
```

Saída esperada:

```
Resource: fence-node1 (class=stonith type=fence_magalucloud)
  Attributes: fence-node1-instance_attributes
    api_key=<API_KEY>
    plug=<VM_ID_NODE1>
    region=<regiao>
  Operations:
    monitor: fence-node1-monitor-interval-60s
      interval=60s
Resource: fence-node2 (class=stonith type=fence_magalucloud)
  Attributes: fence-node2-instance_attributes
    api_key=<API_KEY>
    plug=<VM_ID_NODE2>
    region=<regiao>
  Operations:
    monitor: fence-node2-monitor-interval-60s
      interval=60s
```

---

## 15. Habilitar o STONITH no cluster

```bash
sudo pcs property set stonith-enabled=true
```

---

## 16. Verificar o recurso de fencing

```bash
sudo pcs stonith
```

```bash
sudo pcs status
```

Saída esperada:

```
Full List of Resources:
  * fence-node1  (stonith:fence_magalucloud):  Started $HOSTNAME_NODE2
  * fence-node2  (stonith:fence_magalucloud):  Started $HOSTNAME_NODE1
```

---

## 17. Interface web — pcs-web-ui (opcional)

Execute em um dos nós:

```bash
git clone https://github.com/ClusterLabs/pcs-web-ui.git
cd pcs-web-ui
```

Corrigir registry npm (necessário em alguns ambientes):

```bash
npm config set registry https://registry.npmjs.org/
echo "registry=https://registry.npmjs.org/" > packages/app/.npmrc
```

Limpeza e build:

```bash
rm -rf packages/app/node_modules packages/app/package-lock.json ~/.npm
cd packages/app && npm install --package-lock-only && cd ../..
./autogen.sh && ./configure && make && sudo make install
```

Acesso via browser:

```
https://$IP_NODE1:2224
```

Ou via SSH tunnel:

```bash
ssh -f -N \
  -L 2224:localhost:2224 \
  -i ~/.ssh/<chave.pem> \
  <usuario>@$IP_NODE1
```

Acesse em seguida: `https://localhost:2224`

---

## Validação da saúde do cluster

### Estado completo

```bash
sudo pcs status
```

Saída esperada com fencing configurado e cluster saudável:

```
Cluster name: mycluster
Status of pacemakerd: 'Pacemaker is running' (last updated ...)
Cluster Summary:
  * Stack: corosync (Pacemaker is running)
  * Current DC: $HOSTNAME_NODE1 (version ...) - partition with quorum
  * 2 nodes configured, 2 resource instances configured

Node List:
  * Online: [ $HOSTNAME_NODE1 $HOSTNAME_NODE2 ]

Full List of Resources:
  * fence-node1  (stonith:fence_magalucloud):  Started $HOSTNAME_NODE2
  * fence-node2  (stonith:fence_magalucloud):  Started $HOSTNAME_NODE1

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
