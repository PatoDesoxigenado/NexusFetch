# 🔻 Nexus Fetch

Um aplicativo desktop moderno, rápido e sem complicações para baixar mídias de diversas plataformas (YouTube, Twitter/X e Instagram). Com uma interface limpa desenvolvida em **CustomTkinter** (tema escuro de alto contraste em Vermelho, Preto e Branco), você pode baixar vídeos, áudios (MP3), animações (.GIF) e imagens em resolução máxima, sem precisar lidar com linhas de comando.

---

## ✨ Funcionalidades Principais

- **Interface Moderna e Fluida (CustomTkinter):**
  - Paleta de cores exclusiva (Vermelho Nexus `#E50914`, Preto profundo `#0D0E11` e Branco).
  - Cantos arredondados, animações de *hover* e layout totalmente responsivo com área rolável inteligente.
  - O botão de download (`⚡ BAIXAR AGORA`) e a barra de progresso ficam permanentemente ancorados no rodapé, nunca desaparecendo mesmo se a janela for redimensionada.
- **Detecção Cruzada Inteligente de Links:**
  - Se você estiver na aba do YouTube e colar um link do Twitter/X ou Instagram (ou vice-versa), o app reconhece a plataforma de destino e exibe um botão interativo: `[ Ir para Twitter / X e Analisar ➜ ]`. Ao clicar, a aba troca e a análise inicia automaticamente.
- **Limpeza Automática de Cache a Cada Análise:**
  - Cada vez que você clica em "Analisar", o cache temporário é redefinido e o card de prévia é renovado do zero, evitando travamentos ou sobreposição de capas de links anteriores.
- **Suporte Abrangente no Módulo Twitter / X:**
  - **Fotos e Imagens:** Detecção e download de posts com fotos em resolução original (`.jpg`/`.png`).
  - **Animações (.GIF):** Reconhecimento de GIFs com opção de download direto como `.gif` (gerado com paleta de 256 cores via FFmpeg) ou `.mp4`.
  - **Thumbnail Confiável:** Extração automática do primeiro frame (`00:00:00.1`) via FFmpeg para prévia instantânea da mídia.
- **Módulo Instagram (Fotos, Carrosséis e Vídeos/Reels):**
  - **Fotos e Posts:** Extração inteligente e download de imagens em resolução máxima original (`.jpg`), com contorno transparente de restrições de login/TLS.
  - **Reels e Vídeos:** Download direto em formato `.mp4` de alta qualidade.
  - **Metadados Completos:** Título, autor e capa carregados instantaneamente.
- **Módulo YouTube & Playlists:**
  - Download de Vídeo (MP4) com seleção de resoluções dinâmicas (720p, 1080p, 1440p até 4K UHD).
  - Download de Áudio puro (MP3) com conversão automática na qualidade máxima de 320 kbps e metadados ID3.
  - **Suporte Completo a Playlists:**
    - Extração ultra-rápida de todos os vídeos da playlist em lote.
    - **Lista Interativa Paginada:** Exibe até 30 vídeos por seção com controles de página (`◀ Anterior` e `Próxima ▶`).
    - **Controle Individual de Seleção:** Checkboxes por vídeo para escolher exatamente quais vídeos baixar, evitando downloads indesejados.
    - **Ações Rápidas:** Botões para `Marcar Todos` e `Desmarcar Todos` com persistência de estado entre páginas.
    - Organização automática dos downloads na pasta com o nome da playlist (`01 - Nome.mp4`, `02 - Nome.mp4`, etc.).
  - Download de Thumbnail em alta resolução com um clique.
- **Prévia de Tamanho Estimado de Arquivo:**
  - O menu de seleção de qualidade exibe o tamanho aproximado de cada arquivo antes de iniciar o download (ex: `1080p (FHD) ~ 136.1 MB`, `MP3 320 kbps ~ 8.7 MB`, `Imagem ~ 201.5 KB`).
- **Auto-Diagnóstico de Inicialização & Instalação Automática do FFmpeg (1-Clique):**
  - Ao abrir o app (inclusive no executável), uma rotina instantânea verifica a presença do `FFmpeg`, conexão com a internet e permissões de escrita.
  - **Instalador Automático do FFmpeg:** Caso o computador não tenha o FFmpeg, o app oferece um botão de instalação automática direta que baixa, extrai e configura os binários do FFmpeg sem que o usuário precise abrir o navegador ou configurar variáveis de ambiente.

---

## 🎨 Paleta de Cores e Design

- **Fundo da Janela:** `#0D0E11` (Preto profundo)
- **Cards e Seções:** `#16171B` e `#1F2126` (Carvão suave)
- **Acento Primário (Brand Red):** `#E50914` (Vermelho vibrante)
- **Hover Primário:** `#B80710`
- **Texto Principal:** `#FFFFFF` (Branco absoluto)
- **Texto Secundário / Labels:** `#9CA3AF` (Cinza neutro)

---

## 🚀 Como Executar em Ambiente de Desenvolvimento

### Pré-requisitos
- **Python 3.9+** (recomendado Python 3.11+)
- **FFmpeg** instalado e adicionado ao PATH do sistema

### Instalação
```bash
# 1. Clone ou baixe o repositório
git clone https://github.com/seu-usuario/NexusFetch.git
cd NexusFetch

# 2. Instale as dependências
pip install -r requirements.txt

# 3. Execute o programa
python main.py
```

---

## 🧪 Testes Automatizados

O projeto conta com suíte de testes unitários para validadores regex, extração de metadados, estimativa de tamanhos e rotinas de diagnóstico:

```bash
python -m pytest tests/
```

---

## 📦 Compilação para Executável Standalone

### 🪟 1. Compilação para Windows (.exe)
Gera um executável portátil de um único arquivo na pasta `dist/NexusFetch.exe`, sem janela preta de console (`--noconsole`) e com ícone embutido:

- **Via Script Python:**
  ```cmd
  python build_exe.py
  ```
- **Via Arquivo Batch (1 clique):**
  Dê um duplo clique no arquivo `build.bat`.

---

### 🐧 2. Compilação para Linux (Binário ELF)
Para gerar o executável nativo de sistemas Linux (`dist/NexusFetch`):

> **⚠️ Importante sobre o Git Bash:** O Git Bash no Windows executa o Python do Windows (gerando `.exe`). Para compilar um binário nativo de Linux (formato ELF), execute em uma máquina Linux real ou pelo WSL do Windows.

- **Opção A: Em uma máquina ou Máquina Virtual Linux (Ubuntu, Debian, Fedora, Arch):**
  ```bash
  chmod +x build_linux.sh
  ./build_linux.sh
  ```
  *(Ou: `python3 build_linux.py`)*

- **Opção B: No Windows via WSL (Windows Subsystem for Linux):**
  ```cmd
  wsl -d Ubuntu -- bash -c 'cd "$(wslpath -u "$PWD")" && ./build_linux.sh'
  ```

- **Integração com Desktop Linux:**
  O arquivo [NexusFetch.desktop](file:///C:/Users/Luiz/Documents/GitHub/NexusFetch/NexusFetch.desktop) já está incluso na raiz para integrar o aplicativo ao menu de programas e barra de tarefas do sistema operacional Linux.

---

## 📁 Estrutura do Projeto

```
NexusFetch/
├── README.md                # Documentação completa do sistema
├── requirements.txt         # Dependências do projeto
├── main.py                  # Ponto de entrada da aplicação
├── build_exe.py             # Script de compilação para Windows (.exe)
├── build.bat                # Script em lote para compilação rápida no Windows
├── build_linux.py           # Script de compilação para Linux (Python)
├── build_linux.sh           # Script de compilação para Linux (Bash)
├── NexusFetch.desktop       # Atalho XDG de menu para sistemas Linux
├── assets/                  # Ícones e recursos visuais (.ico e .png)
├── src/
│   ├── config.py            # Configurações globais, paths e constantes
│   ├── utils/
│   │   ├── helpers.py       # Formatação de bytes, tempo e nomes de arquivos
│   │   ├── diagnostics.py   # Checagem de ambiente (FFmpeg, internet, escrita)
│   │   └── validators.py    # Validação regex e detecção cruzada inteligente
│   ├── core/
│   │   ├── metadata.py      # Extração de metadados, frames e renovação de cache
│   │   └── downloader.py    # Motor de download assíncrono (Vídeo, Áudio, GIF, Imagem)
│   └── ui/
│       ├── app.py           # Janela principal com área rolável e botão ancorado
│       ├── theme.py         # Paleta de cores, tipografia e design system
│       └── components/      # Componentes modulares (Navbar, Preview, FormatBar, Progress)
└── tests/                   # Suíte de testes automatizados com pytest
```
