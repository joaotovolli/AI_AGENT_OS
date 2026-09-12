# Criar AI_AGENT_OS_1, AI_AGENT_OS_2 e outras instâncias

Uma instância deve ter seu próprio repositório, diretório Linux, porta e serviços. Copiar apenas
a pasta sem alterar `origin` faria duas instâncias publicarem no mesmo repositório.

O comando abaixo usa os arquivos versionados da instância atual para criar um novo repositório
privado. Ele remove o checkpoint e a evidência da instância anterior; nunca copia tokens, banco
local, logs ou configurações privadas.

```bash
python3 scripts/new_instance.py joaotovolli/AI_AGENT_OS_1 ~/projects/AI_AGENT_OS_1
cd ~/projects/AI_AGENT_OS_1
bash scripts/install-wsl.sh 8766
```

Use `AI_AGENT_OS_2` com a porta `8767`, e assim por diante. Rode também o instalador Windows com
o nome correto de cada instância se quiser atalhos e inicialização automática. Cada nova
instância executa seu próprio bootstrap antes dos goals de usuário.

O script exige um destino que não existe e permissões do `gh` para criar o repositório. O novo
repositório tem histórico próprio. Para usar apenas o template básico, execute o script a
partir de uma cópia limpa do AI_AGENT_OS original, em vez de uma instância com trabalho de projeto.

Instâncias no mesmo WSL2 compartilham acesso ao sistema e a franquia da conta Codex. Portas e
bancos separados evitam conflito de operação; não fornecem isolamento de segurança. Mudanças
globais de pacotes, serviços ou configuração precisam ser coordenadas pelos goals.
