# Definir e acompanhar goals

No dashboard, preencha o título, o resultado desejado e os critérios de conclusão. Você pode
adicionar comandos de verificação, um por linha. Eles são comandos reais de Bash executados
no diretório do repositório, com as permissões da instância.

Exemplo:

| Campo | Conteúdo |
| --- | --- |
| Título | Criar um organizador local de documentos |
| Resultado | Construir uma interface para classificar documentos de uma pasta de teste, com pré-visualização antes de mover os arquivos. |
| Critérios | Arquivos de teste são classificados corretamente; nomes repetidos não sobrescrevem arquivos; a interface mostra o resultado; as instruções de acesso estão no GitHub. |
| Comando opcional | `python3 -m unittest discover -s workspace/tests -v` |

Sem comandos específicos, a suíte do controlador continua obrigatória e uma sessão separada
do Codex precisa verificar os critérios e a evidência do projeto. Critérios vagos tornam essa
verificação menos forte. Para trabalhos verificáveis por código, forneça testes de aceitação.

Goals adicionados durante bootstrap ficam na fila. Depois, o primeiro goal de usuário pendente
mantém prioridade até terminar ou ser cancelado, inclusive quando estiver aguardando quota.
Novos goals não interrompem uma tentativa já em andamento. O botão **Pausar** interrompe a
execução e preserva o trabalho; **Retomar** continua. **Executar agora** antecipa uma nova
tentativa ou o próximo ciclo de manutenção, sem ignorar uma pausa ativa.

O agente mantém tentativas sem limite de quantidade. Cada tentativa tem timeout, grava o que
aprendeu e pode alterar a estratégia seguinte. Falhas de autenticação, modelo, quota ou rede
aparecem no dashboard e geram novas tentativas com espera crescente.

Uma indicação de 100% enviada pelo agente é limitada a 99% até a verificação final. Só o
controlador marca conclusão, após testes, revisão independente e GitHub. Não existe promessa
de que todo goal é possível ou de que a avaliação da IA é infalível.

Os goals e resumos são publicados no repositório. Não coloque segredos na descrição. Para
arquivo confidencial, indique seu caminho local e descreva apenas o necessário. Instruções
de operação e resultados ficam em `docs/`; artefatos do projeto ficam em `workspace/`.
