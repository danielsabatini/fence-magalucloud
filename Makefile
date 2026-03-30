AGENT_SRC   := src/fence_magalucloud/fence_magalucloud.py
FENCING_SRC := src/fence_magalucloud/fencing.py
SBIN_DIR    := /usr/sbin

.PHONY: install update uninstall

## Instala o agente em /usr/sbin (executar dentro do diretório clonado)
install:
	@echo "==> Instalando dependências do sistema..."
	sudo apt install -y fence-agents-common
	@echo "==> Instalando arquivos em $(SBIN_DIR)..."
	sudo cp $(AGENT_SRC) $(SBIN_DIR)/fence_magalucloud
	sudo cp $(FENCING_SRC) $(SBIN_DIR)/fencing.py
	sudo chmod +x $(SBIN_DIR)/fence_magalucloud
	@echo "==> Instalação concluída."
	@echo "    Agente: $(SBIN_DIR)/fence_magalucloud"
	@echo "    Lib:    $(SBIN_DIR)/fencing.py"

## Atualiza a instalação com a versão mais recente do repositório
update:
	@echo "==> Atualizando repositório..."
	git pull
	@echo "==> Atualizando arquivos em $(SBIN_DIR)..."
	sudo cp $(AGENT_SRC) $(SBIN_DIR)/fence_magalucloud
	sudo cp $(FENCING_SRC) $(SBIN_DIR)/fencing.py
	sudo chmod +x $(SBIN_DIR)/fence_magalucloud
	@echo "==> Atualização concluída."

## Remove o agente instalado
uninstall:
	@echo "==> Removendo arquivos instalados..."
	sudo rm -f $(SBIN_DIR)/fence_magalucloud $(SBIN_DIR)/fencing.py
	@echo "==> Desinstalação concluída."
