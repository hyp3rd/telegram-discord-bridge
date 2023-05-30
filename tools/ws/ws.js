let socket = new WebSocket("ws://localhost:8000/api/v1/bridge/health/ws");

socket.onopen = function (e) {
    console.log("[open] Connection established");
    console.log("Sending health request");
};

socket.onmessage = function (event) {
    console.log(`[message] Health data received from server: ${event.data}`);
};

socket.onerror = function (error) {
    console.log(`[error] ${error.message}`);
};

socket.onclose = function (event) {
    if (event.wasClean) {
        console.log(`[close] Connection closed cleanly, code=${event.code} reason=${event.reason}`);
    } else {
        console.log('[close] Connection died');
    }
    // socket.close();
};
