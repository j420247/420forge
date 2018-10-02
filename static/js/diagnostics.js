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
    var dlThreadDumpLinksRequest = new XMLHttpRequest();
    dlThreadDumpLinksRequest.open("GET", baseUrl + "/dogetthreaddumplinks/" + stack_name, true);
    dlThreadDumpLinksRequest.setRequestHeader("Content-Type", "text/xml");
    dlThreadDumpLinksRequest.onreadystatechange = function () {
        if (dlThreadDumpLinksRequest.readyState === XMLHttpRequest.DONE && dlThreadDumpLinksRequest.status === 200) {
            var threaddumpDialog = document.getElementById("threaddump-dialog-content");
            while (threaddumpDialog.firstChild) {
                threaddumpDialog.removeChild(threaddumpDialog.firstChild);
            }
            var urls = JSON.parse(dlThreadDumpLinksRequest.responseText);
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
    };
    dlThreadDumpLinksRequest.send();
}