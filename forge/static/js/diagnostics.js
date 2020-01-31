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
            enableActionButton();
        }, false);
    }
}

function threadDumps() {
    var stack_name = $("#stackName").text();
    send_http_get_request([baseUrl, 'dothreaddumps', region, stack_name].join('/'));
    redirectToLog(stack_name);
}

function heapDumps() {
    var stack_name = $("#stackName").text();
    send_http_get_request([baseUrl, 'doheapdumps', region, stack_name].join('/'));
    redirectToLog(stack_name);
}

function dlThreadDumps() {
    var stack_name = $("#stackName").text();
    send_http_get_request([baseUrl, 'dogetthreaddumplinks', region, stack_name].join('/'), displayThreaddumpsToDownload);
}

function displayThreaddumpsToDownload(responseText) {
    var threaddumpDialog = document.getElementById("threaddump-dialog-content");
    while (threaddumpDialog.firstChild) {
        threaddumpDialog.removeChild(threaddumpDialog.firstChild);
    }
    var urls = JSON.parse(responseText);
    if (urls.length == 0) {
        var text = document.createTextNode("No thread dumps exist for this stack");
        text.className = "threaddump-url";
        document.getElementById("threaddump-dialog-content").appendChild(text);
    }

    var ul = document.createElement("UL");
    ul.className = "aui-list-truncate";

    for (var url in urls) {
        var li = document.createElement("LI");
        var anchor = document.createElement("A");
        var stringUrl = urls[url].substr(urls[url].lastIndexOf("/")+1);
        stringUrl = stringUrl.substr(0, stringUrl.indexOf("?"));
        var text = document.createTextNode(stringUrl);
        anchor.appendChild(text);
        anchor.href=urls[url];
        li.appendChild(anchor);
        ul.appendChild(li);
    }
    document.getElementById("threaddump-dialog-content").appendChild(ul);
    AJS.dialog2("#threaddump-dialog").show();
}