function onReady() {
    $("#stackInformation").hide();
    var stacks = document.getElementsByClassName("selectStackOption");

    for (var i = 0; i < stacks.length; i ++) {
        stacks[i].addEventListener("click", function (data) {
            $("#threadDumpBtn").attr("aria-disabled", false);
            $("#heapDumpBtn").attr("aria-disabled", false);
            selectStack(data.target.text);
        }, false);
    }
}

function threadDumps() {
    var stack_name = $("#stackName").text();
    var threadDumpRequest = new XMLHttpRequest();
    threadDumpRequest.open("GET", baseUrl + "/dothreaddumps/" + region + "/" + stack_name, true);
    threadDumpRequest.setRequestHeader("Content-Type", "text/xml");
    threadDumpRequest.send();

    // Wait a mo for action to begin  in backend
    setTimeout(function () {
        // Redirect to action progress screen
        window.location = baseUrl + "/actionprogress/" + action + "?stack=" + stack_name;
    }, 1000);
}

function heapDumps() {
    var stack_name = $("#stackName").text();
    var heapDumpRequest = new XMLHttpRequest();
    heapDumpRequest.open("GET", baseUrl + "/doheapdumps/" + region + "/" + stack_name, true);
    heapDumpRequest.setRequestHeader("Content-Type", "text/xml");
    heapDumpRequest.send();

    // Wait a mo for action to begin  in backend
    setTimeout(function () {
        // Redirect to action progress screen
        window.location = baseUrl + "/actionprogress/" + action + "?stack=" + stack_name;
    }, 1000);
}