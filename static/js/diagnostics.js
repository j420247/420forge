function onReady() {
    $("#stackInformation").hide();
    var stacks = document.getElementsByClassName("selectStackOption");

    for (var i = 0; i < stacks.length; i ++) {
        stacks[i].addEventListener("click", function (data) {
            $("#threadDumpBtn").attr("aria-disabled", false);
            $("#threadDumpBtn").removeAttr("disabled");
            $("#dlThreadDumpBtn").attr("aria-disabled", false);
            $("#dlThreadDumpBtn").removeAttr("disabled");
            $("#heapDumpBtn").attr("aria-disabled", false);
            $("#heapDumpBtn").removeAttr("disabled");
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

function dlThreadDumps(s3Bucket) {
    var stack_name = $("#stackName").text();
    // s3Bucket/diagnostics/stack_name/
    var dlThreadDumpLinksRequest = new XMLHttpRequest();
    dlThreadDumpLinksRequest.open("GET", baseUrl + "/dogetthreaddumplinks/" + stack_name, true);
    dlThreadDumpLinksRequest.setRequestHeader("Content-Type", "text/xml");
    dlThreadDumpLinksRequest.onreadystatechange = function () {
        if (dlThreadDumpLinksRequest.readyState === XMLHttpRequest.DONE && dlThreadDumpLinksRequest.status === 200) {
            for (url in json.parse(dlThreadDumpLinksRequest.responseText)) {
                $.ajax({
                    success: function (url) {
                        $('<iframe>', {id: 'idown', src: url}).hide().appendTo('body').click();
                    }
                })
            }
        }
    };
    dlThreadDumpLinksRequest.send();
}