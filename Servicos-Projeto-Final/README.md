# ViajaFácil

ViajaFácil é um chatbot de recomendação de vestimentas para viagens. Você informa o destino e as datas, e ele consulta dados climáticos reais para te dizer o que levar na mala.

---

## O que o projeto faz

A ideia é simples: ninguém quer chegar em Paris no inverno com roupa de verão, ou ir para o Nordeste em agosto carregando um casaco desnecessário. O ViajaFácil resolve isso conversando com você, buscando os dados do clima do seu destino e traduzindo temperatura, chuva e vento em sugestões práticas de roupa.

Você digita algo como "vou para Tóquio de 10 a 20 de abril" e o sistema retorna sugestões personalizadas para aquele período específico naquela cidade. Se a viagem estiver dentro dos próximos 15 dias, ele usa a previsão do tempo real. Se for mais para a frente, ele busca o histórico climático dos últimos 5 anos para aquela época do ano e calcula as médias, informando também se o clima costuma ser estável ou imprevisível naquele período.

---

## Arquitetura geral

O projeto é dividido em duas partes que rodam em containers Docker separados e se comunicam entre si.

**Backend** é uma API feita em Python com FastAPI. Ele recebe a mensagem do usuário, passa para o agente de IA, que decide quando e como chamar a ferramenta de clima, e devolve a resposta final.

**Frontend** é uma aplicação React servida pelo nginx. O usuário interage com ela pelo navegador. Quando o usuário envia uma mensagem, o nginx faz o repasse internamente para o backend, de forma que o navegador nem precisa saber o endereço do backend.

```
Navegador
    |
    | HTTP para localhost:3000
    v
  nginx (frontend)
    |
    | proxy interno para backend:8000
    v
  FastAPI (backend)
    |
    | chama a API de clima (Open-Meteo)
    v
  Resposta volta pelo mesmo caminho
```

Essa arquitetura com proxy no nginx é importante porque evita problemas de CORS (quando o navegador bloqueia chamadas para endereços diferentes da página atual) e mantém o backend acessível apenas internamente, não exposto diretamente à internet.

---

## O agente de IA

O coração do projeto é o agente construído com a biblioteca PydanticAI. Um agente de IA, nesse contexto, é diferente de um simples chatbot que apenas responde perguntas. Ele tem acesso a uma ferramenta real que pode chamar para buscar informações externas, e decide sozinho quando precisa usá-la.

O fluxo funciona assim:

1. O usuário envia uma mensagem.
2. O agente recebe a mensagem junto com um prompt de sistema que define o comportamento dele (como ele deve agir, quais regras seguir, como interpretar os dados climáticos).
3. Se a mensagem contém um destino e datas, o agente chama a ferramenta `get_weather_for_trip` com os parâmetros corretos.
4. A ferramenta retorna os dados climáticos.
5. O agente interpreta esses dados e gera a resposta final em linguagem natural.

Tudo isso acontece em uma única chamada ao modelo de linguagem, que decide internamente se precisa acionar a ferramenta ou não antes de responder.

O modelo de linguagem em si é configurável pelo arquivo `.env`. Por padrão o projeto usa o Groq (que oferece inferência rápida e gratuita), mas também funciona com OpenAI ou HuggingFace.

### Regras que o agente segue

O prompt de sistema define uma série de comportamentos específicos que o agente deve respeitar:

- Ele nunca responde sobre clima sem antes chamar a ferramenta. Se não tiver destino ou data, ele pergunta antes de agir.
- Para viagens com múltiplos destinos (cruzeiros, road trips), ele identifica as principais cidades do roteiro e chama a ferramenta separadamente para cada uma, até no máximo 5 cidades.
- Se a viagem já aconteceu (datas no passado), ele não chama a ferramenta e informa o usuário.
- Se a viagem tiver mais de 180 dias de duração, ele recusa a análise por falta de precisão.
- Se a duração for entre 31 e 180 dias, ele pergunta se o usuário digitou certo antes de prosseguir.
- Quando os dados são históricos, ele comunica a confiabilidade de forma natural, sem expor números técnicos como desvio padrão.

---

## A ferramenta de clima

A ferramenta de clima (`weather.py`) é chamada pelo agente e faz todo o trabalho de buscar e processar os dados. Ela usa a API Open-Meteo, que é gratuita e não exige cadastro.

O primeiro passo é a geocodificação: converter o nome da cidade em coordenadas geográficas (latitude e longitude). Isso é necessário porque a API de clima trabalha com coordenadas, não com nomes.

Depois disso, há dois caminhos dependendo das datas da viagem:

**Previsão real:** se a viagem está dentro dos próximos 15 dias, a ferramenta busca a previsão meteorológica diretamente. Os dados retornados incluem temperatura máxima e mínima, precipitação e velocidade máxima do vento para cada dia.

**Dados históricos:** se a viagem está além dos 15 dias, não existe previsão real disponível. Nesse caso, a ferramenta busca os dados do mesmo período nos últimos 5 anos e calcula as médias diárias. Por exemplo, para uma viagem a Paris de 1 a 7 de junho de 2026, ela vai buscar os dados de 1 a 7 de junho de 2025, 2024, 2023, 2022 e 2021, calcular a média de cada dia e também o desvio padrão, que é usado para indicar o nível de confiança da previsão. Um desvio padrão alto significa que o clima variou bastante entre os anos, ou seja, é difícil prever com certeza.

---

## O frontend

O frontend é feito em React com Vite. A interface é um chat com histórico de conversas mantido em memória durante a sessão (reseta ao recarregar a página, sem necessidade de login).

Funcionalidades principais:

**Histórico de conversas:** o menu lateral (hambúrguer no canto superior esquerdo) mostra todas as conversas da sessão atual. Cada conversa tem seu próprio contexto junto ao backend, então ao selecionar uma conversa antiga o agente ainda lembra o que foi discutido nela.

**Múltiplas conversas:** o botão "Nova conversa" cria uma sessão separada. O título da conversa é gerado automaticamente a partir da primeira mensagem enviada.

**Tema claro/escuro:** configurável pelo toggle no header e persistido no localStorage, ou seja, o tema escolhido é mantido mesmo após fechar e reabrir a aba.

**Sugestões de destino:** na tela inicial, aparecem três sugestões com datas reais calculadas dinamicamente (próximo mês e o seguinte) para facilitar o início da conversa.

---

## Sessões e memória do agente

Cada conversa tem um `session_id` único gerado no frontend. A cada mensagem enviada, o frontend manda esse ID junto com o texto. O backend usa esse ID para recuperar o histórico de mensagens daquela conversa (armazenado em memória no processo do backend) e passa todo o histórico para o agente junto com a nova mensagem.

Isso permite que o agente entenda contexto de mensagens anteriores. Se o usuário perguntou sobre Paris e depois pergunta "e se eu for uma semana antes?", o agente entende que ainda estamos falando de Paris.

Esse histórico existe apenas enquanto o container do backend estiver rodando. Se o backend reiniciar, o histórico é perdido. Isso é intencional para um projeto acadêmico sem banco de dados.

---

## Estrutura de arquivos

```
Projeto_Final/
|
├── compose.yaml            orquestra os dois containers
├── .env                    variáveis de ambiente (não versionar)
├── COMO_RODAR.md           instruções para subir o projeto
|
├── backend/
|   ├── Dockerfile          imagem Python 3.11 com uvicorn
|   ├── requirements.txt    dependências Python
|   ├── main.py             API FastAPI com o endpoint /chat
|   ├── agent.py            configuração do agente PydanticAI
|   └── weather.py          ferramenta de geocodificação e clima
|
└── frontend/
    ├── Dockerfile          build Vite + nginx alpine (multi-stage)
    ├── nginx.conf          serve o React e proxeia /chat para o backend
    ├── package.json        dependências Node
    ├── vite.config.js      configuração do Vite com proxy para dev
    └── src/
        ├── main.jsx        ponto de entrada do React
        ├── App.jsx         toda a lógica e componentes da interface
        └── App.css         estilos com variáveis de tema claro/escuro
```

---

## Tecnologias utilizadas

**Backend**

- Python 3.11
- FastAPI para a API HTTP
- PydanticAI para construção do agente com suporte a ferramentas
- Groq / OpenAI / HuggingFace como provedor do modelo de linguagem
- Open-Meteo API para dados climáticos (gratuita, sem autenticação)
- httpx para requisições HTTP assíncronas
- uvicorn como servidor ASGI

**Frontend**

- React 18
- Vite como bundler
- nginx para servir os arquivos estáticos e fazer proxy para o backend

**Infraestrutura**

- Docker para containerização de cada serviço
- Docker Compose para orquestrar os dois containers juntos