import streamlit as st
import requests, time, json, os
from pydantic import BaseModel
from dotenv import load_dotenv
load_dotenv()
perplexity_api_key = os.environ['PERPLEXITY_API_KEY']

st.header("Prediction Market Assistant")

@st.cache_data 
def load_data():
    page_size, page, all_events = 200, 0, []

    r = requests.get(f"https://api.elections.kalshi.com/trade-api/v2/events?limit={page_size}&with_nested_markets=true")
    response = r.json()
    all_events.extend(response['events'])

    while response['cursor'] != '':
        r = requests.get(f"https://api.elections.kalshi.com/trade-api/v2/events?cursor={response['cursor']}&limit=200&with_nested_markets=true")
        response = r.json()
        all_events.extend(response['events'])     

    return all_events

start_time = time.time()
events = load_data()
st.write(f"Loaded {len(events)} events in {time.time()-start_time} seconds")

search = st.text_input("Search Events")

categories = {}
for event in events:
    category = event['category']
    if category not in categories:
        categories[category] = []
    categories[category].append(event)

category_selectbox = st.selectbox("Categories", sorted(categories.keys()))

@st.dialog("Analysis")
def display_analysis(analysis):
    st.write(analysis)

def evaluate_bet(**data):    
    class Contract(BaseModel):
        ticker: str
        side: str
        bid_price: int
        reason: str
        confidence: int

    headers = {"Authorization": f"Bearer {perplexity_api_key}"}
    payload = {
        "model": "sonar-reasoning-pro",
        "messages": [{
                "role": "system", 
                "content": ("You are a prediction market assistant that must evaluate the current prices for event contracts on Kalshi. For each ticker, tell me if the 'yes' or 'no' contract is underpriced and why. Return a confidence score 0-100 so I know how confident you are in your prediction."
                            "So we just need the ticker for the contract, the side 'yes' or 'no' that is underpriced, the bid price, and reason for our analysis for this contract."
                            "Please output a JSON object containing the following fields: "
                            "side, ticker, bid_price, reason, confidence")
            },
            {"role": "user", "content": data['context']},
        ],
        "response_format": {
            "type": "json_schema", "json_schema": {"schema": Contract.model_json_schema()},
        },
    }

    response = requests.post("https://api.perplexity.ai/chat/completions", headers=headers, json=payload).json()
    content = response["choices"][0]["message"]["content"]

    json_str = content.split("```json")[1].replace('```', '')
    try:
        response_dict = json.loads(json_str)
        key = list(response_dict.keys())[0]
        parsed_response = {'contracts': response_dict[key]}
    except Exception as e:
        json_str = '{"contracts": ' + json_str + '}'
        parsed_response = json.loads(json_str)

    print(parsed_response)
    analysis = ""
    for contract in parsed_response['contracts']:
        analysis += f"Submitting {contract['side']} order for {contract['ticker']} for {contract['bid_price']} cent. {contract['reason']}\n\n"

    display_analysis(analysis)

if search and category_selectbox:
    context_markdown = ""
    for event in categories[category_selectbox]:
        if search.lower() in event['title'].lower():
            st.divider()
            bet_markdown = f"#### {event['title']}\n"
            for market in event['markets']:
                bet_markdown += f"##### {market['yes_sub_title']} - {market['ticker']}\n"
                bet_markdown += f"Yes Bid: {market['yes_bid']}, Yes Ask {market['yes_ask']}\n\n"
                bet_markdown += f"No bid: {market['no_bid']}, No Ask {market['no_ask']}\n"

            st.button("Evaluate Bet", key=event['event_ticker'], on_click=evaluate_bet, kwargs={"ticker": event['event_ticker'], "context": bet_markdown})
            st.markdown(bet_markdown)