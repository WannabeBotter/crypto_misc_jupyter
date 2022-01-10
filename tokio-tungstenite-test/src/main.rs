use tokio::io::{AsyncWriteExt, Result};
use tokio_tungstenite::{connect_async, tungstenite::protocol::Message};
use futures_util::{StreamExt, SinkExt};
use serde_json::{Value};

fn print_type_of<T>(_: &T) {
    println!("{}", std::any::type_name::<T>())
}

#[tokio::main]
pub async fn main() -> Result<()> {
    println!("Hello, tokio-tungstenite!");

    let url = url::Url::parse("wss://ws.lightstream.bitflyer.com/json-rpc").unwrap();

    let (ws_stream, _response) = connect_async(url).await.expect("Failed to connect");
    println!("WebSocket handshake has been successfully completed");

    let (mut write, read) = ws_stream.split();
    print_type_of(&read);

    let message_str = "{\"jsonrpc\":\"2.0\",\"method\":\"subscribe\",\"params\":{\"channel\":\"lightning_executions_FX_BTC_JPY\"}}";
    println!("sending {}", message_str);
    write.send(Message::binary(message_str)).await.unwrap();

    let read_future = read.for_each(|message| async {
        let str = message.unwrap().into_text().unwrap();
        if str.chars().count() > 0 {
            let v: Value = serde_json::from_str(&str).unwrap();
            println!("{:#?}", v);
            //tokio::io::stdout().write((str+"\n").as_bytes()).await.unwrap();
        }
    });
    
    read_future.await;
    Ok(())
}
