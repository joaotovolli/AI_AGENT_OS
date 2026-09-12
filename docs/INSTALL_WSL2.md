# Instalação no WSL2

Use Ubuntu 24.04 ou outra distribuição com Python 3.11+, Git, `gh`, Codex CLI e systemd.
Clone em um diretório Linux, como `~/projects/AI_AGENT_OS`, para manter o banco e os serviços
no filesystem Linux. O agente usa seu login atual do Codex.

## Preparação

```bash
sudo apt-get update
sudo apt-get install -y python3 git gh nodejs npm
npm install -g --prefix "$HOME/.local" @openai/codex
export PATH="$HOME/.local/bin:$PATH"
gh auth login
gh auth setup-git
codex login
```

Se Node/npm já estiverem instalados e funcionando, preserve essa instalação. Caso o pacote atual
do Codex exija Node mais novo que o fornecido pela distribuição, instale uma versão compatível
usando a documentação oficial. Não substitua uma instalação funcional sem necessidade.
Os logins interativos são necessários apenas se não houver autenticação válida. Não coloque
tokens em comandos do histórico, em arquivos versionados ou em mensagens do GitHub.

Verifique systemd:

```bash
ps -p 1 -o comm=
```

Se não retornar `systemd`, adicione ou ajuste a seção abaixo em `/etc/wsl.conf`, preservando
as outras configurações existentes:

```ini
[boot]
systemd=true
```

Depois reinicie essa distribuição pelo Windows. Prefira `wsl --terminate NOME_DA_DISTRO` para
não interromper outras distribuições. A sessão Codex dentro dela também será encerrada; retome
a instalação após abrir o WSL novamente. O mecanismo é documentado pela
[Microsoft](https://learn.microsoft.com/en-us/windows/wsl/systemd).

## Instalar a instância

```bash
mkdir -p ~/projects
cd ~/projects
git clone https://github.com/joaotovolli/AI_AGENT_OS.git
cd AI_AGENT_OS
bash scripts/install-wsl.sh 8765
```

O instalador verifica autenticação e testes, configura sudo sem senha para o usuário Linux,
cria a branch de trabalho, inicia os dois serviços e habilita linger. Ele precisa de acesso
sudo inicial. Essa permissão completa é a solicitada para o agente administrar o WSL2.

O código de setup é idempotente para a mesma instância. Use porta e nome de pasta diferentes
para cada instância. Os serviços capturam o PATH da instalação, incluindo o caminho do Codex.
Se você mover o executável ou o repositório, reinstale os serviços.

## Iniciar com o Windows e criar um atalho

Execute dentro do repositório no WSL:

```bash
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "$(wslpath -w scripts/install-windows-startup.ps1)" -Distro "$WSL_DISTRO_NAME" -RepoPath "$PWD" -Instance "ai_agent_os"
```

Isso cria um atalho na inicialização do seu usuário Windows, mantém a distribuição ativa e
adiciona o atalho do dashboard à área de trabalho. A política de execução é ajustada somente
para esse processo PowerShell. O Windows deve estar ligado, acordado e com o usuário conectado.
O systemd sozinho [não mantém uma instância WSL viva](https://learn.microsoft.com/en-us/windows/wsl/systemd).

## Abrir e acompanhar

Abra o atalho ou execute:

```bash
python3 .agent-os/open.py
```

O navegador abrirá `http://localhost:8765` com autenticação local. O acesso por localhost entre
Windows e WSL é descrito pela [Microsoft](https://learn.microsoft.com/en-us/windows/wsl/networking).
Se o encaminhamento estiver desabilitado na sua configuração WSL, corrija-o antes de declarar
a instalação concluída. Não exponha o servidor em `0.0.0.0` como atalho para esse problema.

A primeira tarefa prepara e testa a própria instância. O estado **Pronto** exige testes, execução
real do Codex, revisão independente, serviços ativos e publicação confirmada no GitHub.
Os detalhes desta máquina ficam em [ACCESS.md](ACCESS.md), gerado pelo instalador.
