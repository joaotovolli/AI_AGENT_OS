# Recuperação e operação

## O dashboard abre, mas o agente não trabalha

Veja o estado de pausa, o próximo horário de tentativa e o erro exibido. Se a quota acabou,
novas tentativas ocorrerão com backoff. Se o login venceu, execute `codex login` ou `gh auth login`
no WSL2 e use **Executar agora**. Se o modelo não existe para sua conta, ajuste o ID pelo dashboard.
Não existe troca automática de modelo ou de credenciais.

O serviço usa o PATH capturado na instalação. Após mover ou reinstalar o Codex em outro caminho,
execute `python3 scripts/install_services.py` novamente. Veja os nomes exatos em [ACCESS.md](ACCESS.md).

## Alteração defeituosa no próprio sistema

O worker usa uma cópia imutável do código aprovado. Editar o código fonte não substitui essa
cópia imediatamente. Se os testes falharem, a tentativa permanece na branch `agent/...` e a
próxima execução tenta corrigir o código usando o controlador anterior.

Uma versão que falha ao iniciar três vezes em menos de 30 segundos por tentativa faz o launcher
restaurar a versão anterior. O registro fica em `.agent-os/recovery.log`. Esse mecanismo protege
falhas de inicialização; erros que só aparecem mais tarde dependem dos testes e do próximo goal
de manutenção. O launcher e o atalho local são copiados na instalação para não dependerem do
código que está sendo editado.

Para rollback manual, pare os dois serviços, troque o symlink `.agent-os/runtime` para o destino
de `.agent-os/previous-runtime` e inicie os serviços novamente. Preserve o código defeituoso na
branch de trabalho para investigação. Não use `git reset --hard` para apagar trabalho pendente.

## GitHub indisponível ou branch divergente

O estado e o código continuam locais. O sistema não inicia novas tentativas pagas enquanto não
consegue acessar o repositório. Uma falha no push deixa o checkpoint pendente. A conclusão não
é confirmada até a publicação funcionar.

Se houve commits remotos independentes, reconcilie as branches sem force push. O agente recebe
o erro de sincronização no próximo contexto e pode resolver uma divergência legítima. Conflitos
que exigem uma decisão externa continuam visíveis. Proteção de branch que impede pushes diretos
também precisa ser resolvida na configuração ou no fluxo de publicação do projeto.

Se o scanner detectar um segredo, remova-o do arquivo e de qualquer commit local ainda não
publicado antes do push. Nunca desative o scanner para forçar a publicação. Credenciais que já
foram publicadas precisam ser revogadas no serviço de origem.

## Recuperar goals em uma cópia nova da mesma instância

Clone a branch que contém o checkpoint mais recente, inclusive `agent/...` se necessário.
Antes de inicializar a nova cópia:

```bash
python3 -m agent_os restore
bash scripts/install-wsl.sh 8765
```

O restore exige banco local vazio e o mesmo repositório de origem. Goals incompletos voltam à
fila; o bootstrap precisa validar a máquina novamente. O checkpoint não contém os logs brutos,
as credenciais ou todos os detalhes históricos do banco. Para recuperação integral do banco,
faça backup local de `.agent-os` usando uma cópia SQLite consistente com os serviços parados.

## Remover a instalação

Pare e desabilite os serviços listados em ACCESS.md; remova os arquivos correspondentes em
`~/.config/systemd/user` e execute `systemctl --user daemon-reload`. Remova o atalho de startup
e o atalho do dashboard no Windows, e encerre o processo de keep-alive dessa instância.

A permissão sudo é compartilhada pelo usuário Linux. Remova
`/etc/sudoers.d/90-ai-agent-os-NOME_DO_USUARIO` somente se nenhuma outra instância depender dela.
Os repositórios GitHub e os arquivos do projeto permanecem preservados até uma exclusão explícita.
