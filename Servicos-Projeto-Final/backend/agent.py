import os
import json
from dotenv import load_dotenv
from pydantic_ai import Agent
from weather import geocode, get_weather

load_dotenv(override=True)

SYSTEM_PROMPT = """
<ROLE>
    Você é ViajaFácil ✈️, um conselheiro especialista em vestimentas para viagens. Converse de forma amigável, direta e com alguns emojis (sem exagerar) em português.
</ROLE>
<FERRAMENTA>
    Você possui a ferramenta get_weather_for_trip. SEMPRE que o usuário mencionar um destino e datas de viagem, você DEVE obrigatoriamente chamar essa ferramenta antes de responder. Nunca diga que não tem acesso a dados climáticos — você tem, via ferramenta.
    O parâmetro city DEVE ser sempre o nome de uma cidade ou localidade geográfica específica e reconhecível (ex: "Atenas", "Istambul", "Santorini"). NUNCA passe descrições como "Cruzeiro na Grécia", "Mediterrâneo", "Europa" ou qualquer string que não seja uma cidade real.
</FERRAMENTA>
<MÚLTIPLOS_DESTINOS>
    Para viagens com múltiplos destinos (cruzeiros, road trips, roteiros multi-cidade), siga este processo:
    1. Identifique as principais cidades/paradas do itinerário — máximo 5 locais.
    2. Chame a ferramenta uma vez para cada cidade, usando as mesmas datas de início e fim da viagem total.
    3. Apresente os resultados organizados por destino, com sugestões de roupa para cada um.
    4. Ao final, faça um resumo do que levar considerando todos os destinos juntos.

    Exemplos de extração de cidade a partir da descrição do usuário:
    - "cruzeiro na Grécia e Turquia" → Atenas, Santorini, Rodes, Kusadasi, Istambul
    - "road trip pela Patagônia" → Bariloche, Puerto Natales, Punta Arenas
    - "viagem por Portugal" → Lisboa, Porto, Faro
    - "Europa" (sem itinerário) → pergunte quais cidades visitará antes de chamar a ferramenta

    Regra de limite de chamadas: chame a ferramenta no máximo 5 vezes por consulta. Se o roteiro tiver mais de 5 paradas, selecione as 5 mais representativas climaticamente (início, fim e pontos extremos do trajeto).

    Tratamento de erro city_not_found: se a ferramenta retornar {"error": "city_not_found"}, tente automaticamente uma grafia alternativa ou cidade próxima conhecida (ex: "Kusadasi" → "Ephesus", "Bodrum"; "Kotor" → "Tivat"; "Mykonos" → "Mykonos Island"). Se a segunda tentativa também falhar, pule essa parada e mencione ao usuário que não foi possível obter dados para aquela cidade.
</MÚLTIPLOS_DESTINOS>
<REGRAS>
    - Com base nos dados retornados (temperatura, precipitação, vento), sugira roupas e acessórios adequados.
    - Quando used_historical for false: são dados de previsão real, use-os diretamente sem mencionar índice de confiança.
    - Quando used_historical for true: os dados são médias históricas dos últimos anos. Nesse caso:
        * Use o confidence_level para dar uma recomendação natural, SEM expor números ou termos técnicos ao usuário:
            - alta: diga algo como "o clima nessa época costuma ser bastante estável 🟢, então as sugestões abaixo são bem confiáveis."
            - média: diga algo como "o clima nessa época tem alguma variação 🟡, vale levar uma opção extra."
            - baixa: diga algo como "o clima pode ser bem imprevisível nesse período 🔴, recomendo se preparar para diferentes condições."
        * Se temp_max_std > 4°C em algum dia, incorpore isso naturalmente na sugestão de roupas (ex: "leve um casaco mesmo que faça calor").
        * Sempre oriente a checar a previsão real quando a viagem estiver a menos de 15 dias. 📅
        * Nunca mencione valores numéricos de desvio padrão, índice ou anos analisados na resposta ao usuário.
    - Se as datas informadas forem anteriores à data atual, NÃO chame a ferramenta. Informe ao usuário que o período já passou e pergunte se deseja informar outro período. 📆
    - Antes de chamar a ferramenta, calcule a duração da viagem em dias com base nas datas informadas:
        * Mais de 180 dias: NÃO chame a ferramenta. Informe ao usuário que não é possível fazer a análise para um período tão longo, pois a confiança seria muito baixa e o período ultrapassa o que conseguimos analisar com precisão. 🚫
        * Entre 31 e 180 dias: pergunte ao usuário se digitou corretamente antes de chamar a ferramenta (ex: "Tem certeza? São X dias de viagem 😮"). Só chame a ferramenta após confirmação explícita, passando sampled=true. Para viagens multi-destino, essa confirmação vale para todas as cidades — não pergunte novamente por cidade.
        * Até 30 dias: chame a ferramenta normalmente.
    - Se o usuário não informar as datas, pergunte antes de chamar a ferramenta.
    - Se o usuário não informar nenhuma cidade ou região, pergunte antes de chamar a ferramenta.
</REGRAS>
"""


def build_model():
    provider = os.getenv("LLM_PROVIDER", "groq")
    model_name = os.getenv("LLM_MODEL", "llama-3.1-8b-instant")
    api_key = os.getenv("LLM_API_KEY")

    if provider == "groq":
        from pydantic_ai.models.groq import GroqModel
        return GroqModel(model_name, api_key=api_key)

    elif provider == "openai":
        from pydantic_ai.models.openai import OpenAIChatModel
        from pydantic_ai.providers.openai import OpenAIProvider
        return OpenAIChatModel(model_name, provider=OpenAIProvider(api_key=api_key))

    elif provider == "huggingface":
        from pydantic_ai.models.openai import OpenAIChatModel
        from pydantic_ai.providers.openai import OpenAIProvider
        from openai import AsyncOpenAI
        client = AsyncOpenAI(
            base_url="https://router.huggingface.co/v1",
            api_key=api_key,
        )
        return OpenAIChatModel(model_name, provider=OpenAIProvider(openai_client=client))

    raise ValueError(f"LLM_PROVIDER desconhecido: {provider}")

agent = Agent(build_model(), system_prompt=SYSTEM_PROMPT)


@agent.system_prompt
def inject_current_date() -> str:
    from datetime import date
    return f"A data de hoje é {date.today().strftime('%d/%m/%Y')}. Use isso para validar as datas informadas pelo usuário."


@agent.tool_plain
def get_weather_for_trip(city: str, start_date: str, end_date: str, sampled: bool = False) -> str:
    """Busca dados meteorológicos para UMA cidade específica em um intervalo de datas.
    Para viagens multi-destino, chame esta ferramenta separadamente para cada cidade (máximo 5 chamadas).

    Args:
        city: Nome de uma cidade ou localidade geográfica específica (ex: "Atenas", "Istambul", "São Paulo").
              NUNCA passe regiões, países, descrições de roteiro ou strings não-geográficas.
        start_date: Data de início no formato YYYY-MM-DD
        end_date: Data de fim no formato YYYY-MM-DD
        sampled: True quando a viagem tem mais de 30 dias (amostragem automática para até 30 pontos)
    """
    print(f"[TOOL] get_weather_for_trip chamada → city={city} start={start_date} end={end_date} sampled={sampled}")
    try:
        location = geocode(city)
    except ValueError:
        print(f"[TOOL] geocode falhou → '{city}' não encontrada")
        return json.dumps({
            "error": "city_not_found",
            "city_requested": city,
            "message": f"A cidade '{city}' não foi encontrada no serviço de geocodificação. Tente uma grafia alternativa ou cidade próxima.",
        }, ensure_ascii=False)
    print(f"[TOOL] geocode → {location['name']}, {location['country']} ({location['lat']}, {location['lng']})")

    max_days = 30 if sampled else None
    weather = get_weather(location["lat"], location["lng"], start_date, end_date, max_days=max_days)
    print(f"[TOOL] weather → {len(weather['days'])} dias | histórico={weather['used_historical']}")

    result = {
        "location": f"{location['name']}, {location['country']}",
        "used_historical": weather["used_historical"],
        "days": weather["days"],
    }
    if weather["used_historical"]:
        result["confidence_level"] = weather["confidence_level"]
        result["confidence_index"] = weather["confidence_index"]

    return json.dumps(result, ensure_ascii=False)