# indoor-geolocator

[English](README.md) · [简体中文](README.zh-CN.md) · **Português** · [Français](README.fr.md) · [Español](README.es.md) · [日本語](README.ja.md) · [Deutsch](README.de.md)

Uma skill para agentes que descobre **onde uma foto de interior foi tirada**: um quarto de hotel, um
apartamento, um restaurante, uma loja, uma estação, um museu, uma sala de aula, um carro. Ela devolve o
local, o endereço, as coordenadas com um raio de erro e um nível de confiança que a evidência realmente
sustenta. Também deixa uma pasta de caso organizada que mostra cada passo do raciocínio.

**Página do projeto e demonstração interativa:** https://ezharjan.github.io/indoor-geolocator/

Anexe uma foto e invoque a skill. Nenhum prompt é necessário. A resposta vem no idioma do usuário e tem
este formato (os valores são ilustrativos):

```
📍 <Local> — <endereço, cidade, país>
   51.044560, -114.064700 (WGS84) ± 60 m · nível: site · confiança: MEDIUM
Por quê: ... as 2 a 4 evidências decisivas, cada uma com sua fonte e como foi verificada
Verificado contra: ... as fotos de referência comparadas, as características que coincidiram, o rival testado
Melhor pista (não verificada): ... um candidato mais fino, suas coordenadas (o ponto mais provável) e o teste que o confirmaria
Alternativas: ... o segundo colocado, sua probabilidade e o teste que os separaria
Não verificado / limites: ... o que não pôde ser checado e por quê
Pasta do caso: .../photo-geolocation (REPORT.md traz todo o raciocínio)
```

## O que ela faz

A skill dá ao modelo um fluxo de trabalho rigoroso, que põe a precisão em primeiro lugar, e uma caixa de
ferramentas de linha de comando (`scripts/igl.py`, Python 3.9+, Pillow). Cada observação entra em um único
registro, e a classificação e a confiança são calculadas a partir desse registro, não afirmadas.

Fotos de interiores são localizadas de forma errada por um punhado de razões, e o fluxo foi construído em
torno delas: um ambiente parecido é tomado pelo lugar, o primeiro candidato plausível é mantido, a saída
de máquina (OCR sobre um tapete, o rótulo de um buscador, uma busca que nunca rodou) é lida como fato, um
objeto portátil é lido como o edifício, uma marca é tomada por uma filial, e a precisão é inventada.

1. **Entrada.** Copia a foto byte a byte. Lê EXIF, GPS, XMP, IPTC, ICC, a miniatura embutida (um recorte
   ou edição aparece), o padrão do nome do arquivo, marcadores de IA e credenciais de conteúdo C2PA, e
   converte o deslocamento UTC em fusos horários. Verifica em cinco segundos quais serviços online a
   caixa de ferramentas alcança.
2. **Hipóteses primeiro.** De duas a quatro hipóteses ordenadas são registradas antes de qualquer saída
   de ferramenta (defesa contra ancoragem).
3. **Ler a foto inteira.**
   - OCR filtrado por precisão (textura não é reportada como texto), códigos QR e códigos de barras com
     interpretação do conteúdo (códigos de pagamento EMV, QR-bills suíços, SEPA, UPI, Wi-Fi, vCards,
     prefixos GS1), mineração de texto (telefones até a cidade, domínios, preços, códigos postais,
     unidades, termos fiscais).
   - Um catálogo de cerca de 200 pistas, lido pelo agente em blocos sobrepostos: portadores de
     identidade (nomes, arte única, a vista), padrões fixos (tomadas, interruptores, encanamento,
     sinalização de segurança) e referências locais (uma pintura de um marco local, um mapa, um
     folheto).
4. **Encontrar candidatos.**
   - **Busca reversa de imagem** sem interface no Yandex, TinEye e Baidu, com Google Lens e Bing por
     meio de uma ferramenta de navegador. Cada resultado é comparado com a foto e classificado como
     **COPY** (a mesma fotografia: procedência), **SAME SCENE** / **PARTIAL** (estrutura coincidente)
     ou **unconfirmed**.
   - **Busca de imagens por texto** (`refs`): buscas de imagens de um local, ou de todos os locais de um
     tipo em uma área. As imagens são comparadas com a foto e exibidas **da mais parecida para a menos
     parecida** (DINOv2), de modo que o local certo aparece mesmo quando nenhuma legenda o descreve. Em
     um teste, duas buscas genéricas por bares de hotel em um estado dos EUA puseram o bar verdadeiro em
     primeiro lugar entre 100 imagens de bares diferentes.
   - Nomes, telefones, URLs e nomes de Wi-Fi com a busca na web do próprio agente; padrões fixos
     cruzados entre 250 países offline; todos os locais de um tipo enumerados a partir do OpenStreetMap
     e do Wikidata; anúncios e redes sociais (com foco em lugares).
5. **Verificar: a barreira entre uma pista e uma resposta.** Um teste de falseamento é escrito primeiro.
   As fotos do próprio candidato são postas ao lado da foto, e características fixas específicas são
   contadas (janelas, teto, móveis embutidos, a vista, arte feita para o local; a mobília prova apenas
   um projeto de decoração). O rival mais próximo passa pela mesma comparação. Se o rival também
   "coincide", as características são um projeto compartilhado: a coincidência é registrada para a área
   do grupo, e os locais continuam sendo pistas.
6. **Consistência.** Fuso horário, sol, clima, estação e padrões são conferidos com o candidato,
   argumenta-se a favor do segundo colocado, e o passo decisivo é refeito de outra forma.
7. **Decisão.** A resposta é o nível mais fino que a evidência verifica. Um local não verificado dentro
   de uma área verificada é reportado como a melhor pista, com suas próprias coordenadas (o ponto mais
   provável), nunca como a resposta. A pasta do caso é finalizada e enxugada.

### Regras de precisão embutidas no código

- **Tetos por status.** O peso de uma pista é limitado pela forma como ela foi obtida: uma inferência
  ≤3, uma observação ≤6, um relato de terceiros ≤10, metadados do arquivo ou uma cópia rastreada da
  foto ≤20, texto lido em um recorte ampliado ou um resultado calculado ≤50, uma coincidência com
  imagens de referência independentes ≤100. O rótulo de um buscador é uma pista (≤3), diga o que disser.
- **Pistas que identificam e pistas de categoria.** Uma pista decisiva (um nome lido na foto, um código
  decodificado, GPS, uma cópia rastreada, uma referência coincidente) identifica um único lugar e é
  pesada contra todas as alternativas juntas: LR 50 significa cerca de 50:1, por mais rivais que
  tenham sido listados. Uma pista de categoria (um tipo de tomada, um idioma, um estilo) compete com
  cada alternativa, uma a uma, de modo que só várias juntas definem um país.
- **Coincidências auditáveis.** Uma pista `matched` precisa nomear pelo menos três características
  fixas específicas e citar o arquivo da comparação. Uma cópia da foto é recusada como coincidência: é
  procedência, registrada como `traced` com sua página.
- **O controle com o rival.** Uma coincidência com referência só chega a HIGH quando um local rival
  passou pela mesma comparação, ou quando uma segunda linhagem decisiva (um nome lido na foto, GPS, uma
  cópia rastreada) aponta o mesmo local.
- **Um local precisa de uma pista decisiva.** Semelhança, rótulos de buscadores e legendas deixam um
  local em LOW, por mais que concordem entre si: essa combinação é exatamente o que um sósia produz.
- **Linhagens independentes.** A concordância só conta entre fontes independentes (image, text,
  metadata, web, engine, map, reference, geometry). Cinco pistas de decoração são uma única linhagem.
- **Um quadro aberto e coerente.** Alternativas não listadas mantêm uma parcela em todos os níveis, uma
  cidade nunca é mais certa do que seu país, e uma contradição contra um país também bloqueia HIGH para
  o hotel dentro dele.
- **Falha honesta.** Uma busca que foi bloqueada ou nunca começou é reportada como tal, nunca como "sem
  resultados". Imagens não confirmadas nunca são chamadas de "diferentes".
- **Barreira de cobertura.** Treze métodos principais precisam terminar, cada um, como results,
  no_results ou not_applicable antes que `check` passe; `check` também sinaliza um local sem comparação
  com referências ou sem rival, um rival que também coincidiu e buscas reversas que nunca rodaram.

## Instalação

**claude.ai, Claude Desktop e Cowork.**
1. Confirme que a execução de código está ativada (*Settings → Capabilities*). O acesso à rede para a
   execução de código ajuda (a caixa de ferramentas então alcança sozinha os serviços de mapas e de
   busca reversa); sem ele, o agente faz esses passos com suas próprias ferramentas de busca na web,
   fetch e navegador.
2. Abra *Customize → Skills*, clique em **+**, escolha **+ Create skill → Upload a skill** e selecione
   `indoor-geolocator.zip`.
3. Anexe uma foto e invoque a skill, ou simplesmente pergunte "onde isto foi tirado?".

O zip contém a pasta `indoor-geolocator/` no nível superior, como o envio exige.

**Claude Code.** Copie a pasta `indoor-geolocator/` para `~/.claude/skills/` (todos os projetos) ou
`<project>/.claude/skills/` (um projeto). Invoque com `/indoor-geolocator`, ou deixe o Claude acioná-la
quando você compartilhar uma foto de interior.

**Outros agentes** (Codex, Gemini CLI, Cursor, …): aponte o agente para `indoor-geolocator/SKILL.md`. A
caixa de ferramentas é uma CLI Python simples.

**Dependências.** Pillow é obrigatório, assim como `tzdata` no Windows. Todo o resto é opcional e apenas
habilita o método correspondente.

```bash
pip install -r indoor-geolocator/requirements.txt             # Pillow (+ tzdata, necessário no Windows)
pip install -r indoor-geolocator/requirements-optional.txt    # OpenCV + numpy, Playwright, onnxruntime, phonenumbers, HEIC, RapidOCR
playwright install chromium                                   # busca reversa sem interface, busca de imagens, capturas de página
# Motor de OCR (recomendado): tesseract com pacotes de idiomas
#   apt install tesseract-ocr-all  |  brew install tesseract tesseract-lang  |  winget install UB-Mannheim.TesseractOCR
python indoor-geolocator/scripts/igl.py doctor                 # o que funciona aqui, o que falta
```

Três extras são os que mais pesam na precisão: OpenCV (os testes COPY / SAME SCENE), Playwright com
Chromium (busca reversa de imagem e busca de imagens) e onnxruntime (imagens ordenadas pela semelhança com
a foto). O modelo de similaridade (DINOv2 ViT-S/14, 24 MB, Apache-2.0) não faz parte da skill: é baixado
uma vez de huggingface.co no primeiro uso e conferido com um SHA-256. `IGL_NO_EMBED=1` o desliga.

## Usando a caixa de ferramentas diretamente

```bash
IGL="python3 indoor-geolocator/scripts/igl.py"
$IGL init photo.jpg                                    # pasta do caso + metadados + grade + teste de rede
$IGL note CASE "Hypotheses: 1) ... 2) ..." --kind hypothesis --status inferred --source image
$IGL scan CASE                                         # OCR, QR/códigos de barras, sinais de texto, blocos de varredura
$IGL crop CASE --cell C3:D4 --enhance auto --label socket
$IGL revsearch CASE --cell B2:C3 --flip                # Yandex, TinEye, Baidu; cada resultado classificado contra a foto
$IGL share CASE --cell B2:C3                           # links para Google Lens e Bing (cópia temporária)
$IGL countries --plug G --currency £ --drive left --case CASE --clue N2
$IGL refs CASE "hotel lounge sea view Poole"           # imagens de uma área inteira, as mais parecidas primeiro
$IGL geo poi --tag tourism=hotel --area "Poole" --case CASE --add site --parent C3
$IGL refs CASE "Hotel Name Poole lounge" --for C12     # as fotos de um candidato ao lado da sua
$IGL compare CASE --refs E14 --pick 3,7 --for C12      # lado a lado em tamanho grande + testes de coincidência
$IGL note CASE "Matches a traveller photo (2023)" --kind match --status matched --source reference --file E16 \
     --features "arched window pair; coffered ceiling 3x4; green marble fireplace" --for C12:60 --why "..."
$IGL refs CASE "Rival Hotel Poole lounge" --for C13    # o controle com o rival
$IGL rank CASE
$IGL answer CASE C12 --summary "..."
$IGL check CASE
$IGL finalize CASE
```

`$IGL <command> -h` documenta todas as opções. No Windows, use `python` em vez de `python3`. Coordenadas
ao sul e a oeste funcionam como digitadas (`--at -33.86,151.21`).

## O que você recebe

```
photo-geolocation/
├── REPORT.md       a resposta, a melhor pista, confiança por nível, evidências, candidatos, linha do tempo, métodos, tratamento de dados
├── result.json     o mesmo em JSON legível por máquina (esquema igl.result/1)
├── case.json       o registro completo: pistas, candidatos, vínculos, exclusões, tentativas, horários
├── input/          a foto (cópia exata) e metadata.json
└── evidence/       apenas os recortes, folhas, comparações e capturas que o registro cita
```

O trabalho de rascunho (blocos, caches, downloads) fica em `.work/` e é apagado por `finalize`, que também
remove todo arquivo de evidência que nada cita. Uma pasta de caso existente nunca é sobrescrita.

## Privacidade e uso responsável

- **Pessoas não são alvos.** Sem reconhecimento facial e sem identificação de indivíduos.
  - Roupas, uniformes, crachás e objetos pessoais são usados apenas pelo que dizem sobre o lugar.
  - A etnia aparente é tratada como contexto fraco e sujeito a viés, nunca como exclusão.
  - As redes sociais são pesquisadas por lugares, texto, tags e pela própria foto, nunca por pessoas
    ou autores de postagens.
- **Residências particulares.** Para uma residência particular identificável sem finalidade declarada,
  a skill pergunta uma vez para que serve o resultado. Sem uma finalidade legítima, ela para no nível
  de cidade ou bairro.
- **Ocultação.** Nomes de particulares e endereços residenciais ficam fora dos relatórios. Senhas de
  Wi-Fi, IBANs e nomes em cartões de contato são ocultados sempre que são decodificados ou devolvidos
  por um buscador ou uma página.
- **Envios.** A busca reversa de imagem envia a foto (sem metadados) aos buscadores. `share` coloca uma
  cópia sem metadados em um host temporário (apagada após 1 a 3 horas) para Lens e Bing, e `revsearch`
  faz o mesmo por conta própria quando o formulário de envio de um buscador falha (`--no-share`
  impede). O relatório lista cada buscador e cada cópia temporária. `refs` envia apenas texto de busca,
  e o modelo de similaridade roda localmente. Prefira recortes sem pessoas; nada é enviado sem
  perguntar quando o usuário marca uma foto como privada.
- **Serviços.** A skill respeita as políticas dos serviços (Nominatim ≤1 requisição/s, consultas
  Overpass limitadas, User-Agent identificável). Ela nunca faz login em nome de ninguém, nunca resolve
  CAPTCHAs e nunca faz coleta em massa. Chaves opcionais do usuário: `SERPAPI_KEY` para Google Lens
  dentro de `revsearch`, `WIGLE_API_NAME` / `WIGLE_API_TOKEN` para consultas de SSID de Wi-Fi.
  `IGL_USER_AGENT` define um User-Agent personalizado.

Os resultados de geolocalização são estimativas ponderadas pela evidência, não certezas. Leia a confiança,
a melhor pista e a linha "não verificado" antes de agir com base em uma resposta.

## Estrutura do repositório

```
.
├── indoor-geolocator/          A skill (esta pasta é o que se instala)
│   ├── SKILL.md                fluxo de trabalho, regras de evidência, conduta, formato da resposta
│   ├── LICENSE.txt             cópia de LICENSE (o zip vai sem a raiz do repositório)
│   ├── requirements*.txt
│   ├── references/             catálogo de pistas, roteiros de cenas e de busca, janela/luz, verificação,
│   │                           evidência e confiança, fontes e ferramentas
│   ├── scripts/igl.py          a CLI; scripts/iglib/ contém seus módulos
│   └── data/                   countries.json, gs1_prefixes.json (+ README com fontes e licenças)
├── indoor-geolocator.zip       a mesma skill, empacotada para envio
├── build_skill_zip.py          reconstrói e verifica o zip (rode após cada mudança na skill)
├── tools/build_data.py         ferramenta de manutenção: reconstrói data/ a partir do Unicode CLDR e da Wikipédia
├── tools/make_demo.py          ferramenta de manutenção: reconstrói docs/demo/ com a versão atual
├── tests/                      suíte de testes offline (pytest; `pytest.ini` aponta para ela)
├── docs/                       página do projeto (GitHub Pages) com o caso de demonstração publicado
├── LICENSE
├── README.md                   este README em inglês
└── README.*.md                 traduções (zh-CN, pt-BR, fr, es, ja, de)
```

## Desenvolvimento

```bash
python -m pytest                   # testes offline: regras do registro, tetos, coincidência, ordenação, parsers, geometria;
                                   # e também docs vs CLI, o zip vs a pasta da skill, a página do projeto vs o caso de demonstração
python tools/build_data.py         # atualiza data/ (guarda as fontes em cache em .data-src/; --offline reconstrói do cache)
python tools/make_demo.py          # reconstrói o caso de demonstração em docs/demo/ com a versão atual
python build_skill_zip.py          # reconstrói indoor-geolocator.zip se a pasta mudou; --check apenas verifica
```

## Histórico de mudanças

### 2.0.0

A versão da precisão: construída contra a resposta errada mais comum, um local sósia nomeado com confiança.

- **Encontrar.** Novo comando `refs`: busca de imagens por texto (Brave, Startpage) e páginas de
  galeria, com cada imagem comparada com a foto. Imagens e resultados de busca reversa são ordenados
  por similaridade visual (DINOv2, opcional), de modo que as referências mais prováveis são os
  primeiros blocos que o agente vê.
- **Busca reversa.** Cada resultado é classificado como COPY / SAME SCENE / PARTIAL / unconfirmed
  contra a foto. Uma busca que nunca começou é `unavailable`, não `no_results`; alternativa por URL
  quando um formulário de envio falha; Google Lens opcional pela chave SerpApi do usuário.
- **Verificação.** Pistas `matched` precisam nomear três características e citar a comparação; cópias
  são recusadas como coincidências e registradas como procedência `traced`; `compare --refs E## --pick`;
  o controle com o rival é exigido para HIGH; coincidências de projeto são registradas para a área, com
  os locais como pistas.
- **Confiança.** Pistas decisivas são pesadas contra o campo inteiro (um local verificado não é mais
  diluído por países não listados nem pelos rivais que o agente enumerou); um local precisa de uma
  pista decisiva para MEDIUM; rótulos de buscadores têm teto 3; contradições bloqueiam HIGH ao longo da
  cadeia; um lugar é pelo menos tão certo quanto o lugar verificado dentro dele.
- **Leitura.** A saída do OCR é filtrada por precisão (acabou o "texto" e as escritas exóticas lidas em
  tapetes e tetos); `scan` grava uma folha com os recortes de texto; `crop --of` amplia qualquer imagem
  de evidência.
- **Robustez.** Alternativa Photon quando o Overpass está inacessível, downloads com novas tentativas,
  relato de limites de taxa por execução, métodos implicados pelas pistas registradas, `log` com listas
  separadas por vírgula.
- **Saída.** Um marcador de melhor estimativa (as coordenadas da pista quando a resposta é mais
  grosseira), uma seção de verificação com o controle do rival no relatório, tabelas de candidatos que
  dizem o que é cada linha (a resposta, um lugar que a contém, a pista não verificada, as alternativas
  fora do quadro), `tools/make_demo.py` para reconstruir o caso de demonstração, e testes que mantêm a
  página do projeto fiel a esse caso e o zip fiel à pasta da skill.

### 1.1.0

Não recebeu tag nem versão própria: estas mudanças são publicadas pela primeira vez com a 2.0.0.

- Fluxo reordenado em torno de rotas de coincidência exata e de uma barreira de verificação; hipóteses
  antes da saída das ferramentas; divisão de trabalho entre a caixa de ferramentas e as ferramentas de
  busca na web, fetch e navegador do próprio agente.
- Pontuação: um quadro aberto em todos os níveis, parcelas coerentes ao longo da cadeia, pistas de
  categoria não sobem de nível, barreira na resposta com uma melhor pista separada, checagens antes do
  relatório.
- Busca reversa: Baidu adicionado, folhas de contato de imagens semelhantes, `share` para Lens e Bing
  por URL.
- `compare`: testes de quase duplicata, de mesma fotografia e geométricos SIFT/RANSAC, com ambientes
  espelhados.
- Teste de rede em `init`; `geo ... --print-url`; `note --for/--against` em uma única chamada; leitor
  de C2PA.

### 1.0.0

Primeira versão pública.

## Licença

O código e a documentação são publicados sob a [MIT License](LICENSE). Os arquivos de dados em
`indoor-geolocator/data/` mantêm as licenças de suas fontes:
- Campos do Unicode CLDR: [Unicode License v3](https://www.unicode.org/license.txt).
- Campos derivados da Wikipédia (tipos de tomada, rede elétrica, mão de direção, números de emergência,
  prefixos GS1): [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/), © colaboradores da
  Wikipédia.

Os detalhes estão em [indoor-geolocator/data/README.md](indoor-geolocator/data/README.md).

Ideias de projeto foram adaptadas dos projetos de código aberto geo-sleuth, Geo-Guesser e Searching-skill:
regras impostas em código, um quadro de candidatos por razão de verossimilhança, evidência graduada por
linhagem, uma barreira de cobertura de métodos, "a máquina ordena primeiro" com uma ordem de similaridade
DINOv2, e verificação SIFT/RANSAC. O modelo de similaridade é o DINOv2 (Meta AI, Apache-2.0) na exportação
ONNX publicada como `Xenova/dinov2-small`; ele é baixado em tempo de execução e não é redistribuído aqui.
