use std::collections::HashMap;
use tokio::io::{AsyncWriteExt, Result};
use tokio_tungstenite::{connect_async, tungstenite::protocol::Message};
use futures_util::{StreamExt, SinkExt};

use serde::Deserialize;
use serde_with::{serde_as, TimestampSecondsWithFrac};
use chrono::{DateTime, Utc};

use rust_decimal::prelude::*;

pub type Id = u64;
pub type Coin = String;
pub type Symbol = String;

#[derive(Clone, Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct Response {
    pub market: Option<Symbol>,
    pub r#type: Type,
    pub data: Option<ResponseData>,
}

#[derive(Copy, Clone, Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
pub enum Type {
    Subscribed,
    Unsubscribed,
    Update,
    Error,
    Partial,
    Pong,
    Info,
}

#[derive(Clone, Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
#[serde(untagged)]
pub enum ResponseData {
    OrderbookData(OrderbookData),
}

#[serde_as]
#[derive(Clone, Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct OrderbookData {
    pub action: OrderbookAction,
    // Note that bids and asks are returned in 'best' order,
    // i.e. highest to lowest bids, lowest to highest asks
    pub bids: Vec<(Decimal, Decimal)>,
    pub asks: Vec<(Decimal, Decimal)>,
    pub checksum: Checksum,
    #[serde_as(as = "TimestampSecondsWithFrac<f64>")]
    pub time: DateTime<Utc>, // API returns 1621740952.5079553
}

type Checksum = u32;

#[derive(Copy, Clone, Debug, Deserialize, PartialEq)]
#[serde(rename_all = "camelCase")]
pub enum OrderbookAction {
    /// Initial snapshot of the orderbook
    Partial,
    /// Updates to the orderbook
    Update,
}

#[tokio::main]
pub async fn main() -> Result<()> {
    println!("Hello, tokio-tungstenite!");

    let url = url::Url::parse("wss://ftx.com/ws/").unwrap();

    let (ws_stream, _response) = connect_async(url).await.expect("Failed to connect");
    println!("WebSocket handshake has been successfully completed");

    let (mut write, read) = ws_stream.split();

    let message_str = "{\"op\": \"subscribe\", \"channel\": \"orderbook\", \"market\": \"XRP-PERP\"}";
    println!("sending {}", message_str);
    write.send(Message::binary(message_str)).await.unwrap();

    let bids_hash: HashMap<Decimal, Decimal> = HashMap::new();
    let mut asks_hash: HashMap<Decimal, Decimal> = HashMap::new();
    let latest_timestamp = 0;

    let read_future = read.for_each(|message| {
        let str = message.unwrap().into_text().unwrap();
        if str.chars().count() > 0 {
            let response: Response = serde_json::from_str(&str).unwrap();
            //let v: Value = serde_json::from_str(&str).unwrap();
                        
            println!("v : {:?}", response);

            /*let action = &v["data"]["action"];
            if action.is_string() == true {
                
                let action_str = action.as_str().unwrap();

                if action_str == "partial" {

                    // Put asks to Hashmap
                    let asks_array = v["data"]["asks"].as_array().unwrap();
                    println!("asks_array : {:?}", asks_array);
                    
                    for val in asks_array.iter() {
                        let val_array = val.as_array().unwrap();

                        println!("val[0] : {:?}", val);
                        let price_decimal: Decimal = Decimal::from_str(val_array[0].as_str().unwrap()).unwrap();
                        let amount_decimal: Decimal = Decimal::from_str(val_array[0].as_str().unwrap()).unwrap();
                        asks_hash.insert(price_decimal, amount_decimal);
                    }
                }
            }*/
        }
        async {
            ()
            //println!("{} {} {} {} {}", v["data"][0]["id"], v["data"][0]["liquidation"], v["data"][0]["price"], v["data"][0]["size"], v["data"][0]["time"]);
            //tokio::io::stdout().write((str+"\n").as_bytes()).await.unwrap();
        }
    });
    
    read_future.await;
    Ok(())
}
