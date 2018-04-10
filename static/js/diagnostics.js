function threadDumps() {
    var threadDumpRequest = new XMLHttpRequest();
    threadDumpRequest.open("GET", baseUrl + "/dothreaddumps/" + env + "/" + stackName, true);
    threadDumpRequest.setRequestHeader("Content-Type", "text/xml");
    threadDumpRequest.send();

    // Wait a mo for action to begin  in backend
    setTimeout(function () {
        // Redirect to action progress screen
        window.location = baseUrl + "/actionprogress/" + action + "/" + stackName;
    }, 1000);
}

function heapDumps() {
    var heapDumpRequest = new XMLHttpRequest();
    heapDumpRequest.open("GET", baseUrl + "/doheapdumps/" + env + "/" + stackName, true);
    heapDumpRequest.setRequestHeader("Content-Type", "text/xml");
    heapDumpRequest.send();

    // Wait a mo for action to begin  in backend
    setTimeout(function () {
        // Redirect to action progress screen
        window.location = baseUrl + "/actionprogress/" + action + "/" + stackName;
    }, 1000);
}