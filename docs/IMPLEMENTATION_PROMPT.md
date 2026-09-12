# Prompt de implementação no WSL2

Copie o texto abaixo para uma sessão Codex executada no seu WSL2, com acesso ao host.

---

Instale, valide e coloque em operação o projeto https://github.com/joaotovolli/AI_AGENT_OS.git
no meu WSL2 Linux. Trabalhe até concluir a instalação e a validação real. Não termine apenas
com um plano ou com comandos para eu executar se você puder executá-los.

Autorizo as mudanças necessárias no WSL2, instalação e configuração de dependências, serviços,
sudo sem senha para meu usuário Linux e inicialização do WSL no login do Windows. Preserve
projetos e configurações existentes que não precisem ser alterados. Não publique credenciais.
Essa autorização não remove restrições reais das ferramentas, da conta ou do provedor.

1. Localize uma cópia existente desse repositório. Se não houver, clone em
   ~/projects/AI_AGENT_OS. Confirme que origin corresponde ao repositório correto. Não recrie
   o sistema do zero: leia AGENTS.md, README.md, docs/ARCHITECTURE.md, docs/INSTALL_WSL2.md,
   docs/CODEX.md e docs/VALIDATION.md e continue a implementação existente.

2. Inspecione WSL, systemd, Python, Git, GitHub CLI, Node/npm e Codex CLI. Instale ou ajuste
   somente o necessário. Use a autenticação existente do GitHub e do Codex. Nunca imprima,
   copie para o GitHub ou exponha auth.json, tokens ou arquivos .env. Se um login realmente
   exigir minha interação, explique exatamente qual interação falta. Se systemd exigir
   reiniciar a distribuição, prepare tudo que puder antes e deixe a continuação documentada.

3. Confirme com codex exec --help e uma execução real que o adapter aceita o modelo
   gpt-5.6-luna com reasoning medium. Esse é o padrão obrigatório. Teste a saída JSONL,
   o schema de resultado e o modo de acesso completo. Verifique o controle Fast conforme
   a documentação atual e a disponibilidade da conta; se não for suportado, registre essa
   limitação com clareza. Não troque de modelo silenciosamente e não altere meu config global
   do Codex sem necessidade. Use o login Codex existente, sem criar uma dependência de API key.

4. Execute a suíte de testes e corrija qualquer defeito real. Rode o instalador
   bash scripts/install-wsl.sh 8765, escolhendo outra porta livre apenas se 8765 estiver
   ocupada. Instale os atalhos Windows e o keep-alive usando scripts/install-windows-startup.ps1.
   Confirme que os dois serviços ficam ativos sem um terminal aberto e que o atalho abre
   o dashboard no navegador do Windows. Não declare o startup validado apenas por criar arquivos.

5. Deixe o bootstrap automático trabalhar e acompanhe suas tentativas. Corrija problemas de
   instalação e integração encontrados. Valide no navegador real, incluindo uma tela pequena:
   autenticação, criação de goal, estado da fila, troca de modelo/reasoning/Fast, progresso,
   pausa, retomada e cancelamento. Não remova testes nem reduza critérios para obter aprovação.

6. Depois do bootstrap, crie um goal de teste pequeno e verificável, por exemplo produzir
   um arquivo de exemplo em workspace/smoke-test e um teste que confira seu conteúdo. Observe
   execução real, revisão independente, commit, push e conclusão no dashboard. Teste a retomada
   de um goal interrompido e o tratamento de falhas com os testes automatizados. Teste uma
   manutenção antecipada pelo botão Executar agora e deixe o intervalo final em 3.600 segundos.
   Preserve Luna Medium e Fast desligado ao terminar, salvo se eu instruir outra configuração.

7. Publique o código, as correções e as instruções no GitHub. Toda tentativa deve ter checkpoint
   na branch da instância; mudanças aprovadas devem chegar à branch estável. Não faça force push.
   Registre alterações fora do repositório com scripts e notas sem segredos em infra/. Atualize
   docs/ACCESS.md, docs/VALIDATION.md e a evidência dos goals com os resultados reais desta máquina.
   Verifique também a execução do CI no GitHub. Não coloque os logs brutos ou o banco local no Git.

8. Termine somente quando houver evidência de prontidão: dashboard acessível pelo Windows,
   serviços persistentes, Codex autenticado no modelo solicitado, goal de teste concluído com
   verificação, GitHub sincronizado e manutenção automática ativa. Deixe o agente rodando, pronto
   para receber meu primeiro goal de projeto. Informe a URL, o nome do atalho, os links GitHub e
   qualquer limitação real restante. Não afirme que o sistema ficou perfeito ou sem possibilidade
   de falhas. Se a franquia acabar, preserve e publique o progresso possível, informe o bloqueio
   e mantenha o agendamento de retomada; não tente contornar limites.

O projeto deve continuar reutilizável em AI_AGENT_OS_1, AI_AGENT_OS_2 e outros repositórios.
Preserve o script scripts/new_instance.py e a separação de portas, estado e serviços por instância.
