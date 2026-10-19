# Migração para 3.0.1

O branch principal continha README e licença. Os fontes da versão 2.2.1-beta estavam no ZIP do lançamento anterior, inspecionado durante esta implementação

O novo aplicativo reúne o fluxo de arquivos em uma interface CustomTkinter para Windows. O launcher de console antigo e o editor Tkinter anterior continuam disponíveis nos lançamentos históricos; esta versão não altera os arquivos desses lançamentos

| Versão anterior | 3.0.1 |
| --- | --- |
| Menu de console e OCAT em processo separado | Interface única com editor integrado e possibilidade de abrir o OCAT oficial |
| Fontes executados com Python instalado | Fontes de desenvolvimento e build Windows independente, com instalador |
| Catálogo com atualizações fixas | Acesso ao catálogo oficial da Apple e escolha de recuperação por Board ID/MLB |
| Estimativas amplas de compatibilidade | OHV preliminar, sem percentual e com pendências por dispositivo |
| Campos NVRAM e PlatformInfo em páginas específicas | Edição tipada da estrutura inteira, filtro por seção e diálogo SMBIOS |
| Geração de SMBIOS | macserial oficial selecionado pelo usuário, sem baixar ou executar ferramentas automaticamente |
| Traduções antigas em Python | JSON separado em português e inglês; demais idiomas anteriores não estão incluídos nesta edição |
| Dados junto do script | Preferências e logs em LocalAppData |

Não há importação automática de preferências antigas, pois seus caminhos e formatos variavam entre módulos. Abra a cópia do seu config.plist, configure os caminhos das ferramentas externas e salve suas preferências na nova interface

Um config.plist existente mantém suas chaves e tipos; o aplicativo não faz migração automática do esquema do OpenCore. XML é reserializado e comentários/formatação podem mudar. Arquivos binários permanecem binários. Guarde a EFI anterior para comparação

