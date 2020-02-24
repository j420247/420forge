function onReady() {
    var stacks = document.getElementsByClassName("selectStackOption");
    for (var i = 0; i < stacks.length; i++) {
        stacks[i].addEventListener("click", function (data) {
            var stack_name = data.target.text;
            selectStack(stack_name);
            listNodes(stack_name);
        }, false);
    }    $("#action-button").on("click", performNodeRestart);
}

function listNodes(stack_name) {
    // Add a spinner
    if ($("#nodesList").find(".aui-spinner").length === 0) {
        $("#nodesList").empty();
        var li = document.createElement("li");
        var spinner = document.createElement("aui-spinner");
        spinner.setAttribute("size", "small");
        li.appendChild(spinner);
        $("#nodesList").append(li);
    }
    // If nodes not yet in stack info, sleep 1s
    if ($('#nodes').length > 0 && $('#nodes').find(".aui-spinner").length !== 0) {
        setTimeout(function() {
            listNodes(stack_name)
        }, 1000);
        return;
    }
    // Get nodes
    var nodes = [];
    $.each($('.nodes'), function() {
        nodes.push(this.innerText.substr(0, this.innerText.indexOf(':')));
    });
    // Remove existing nodes/spinner
    $("#nodesList").empty();
    // Add each node to dropdown
    for (var node in nodes) {
        var li = document.createElement("LI");
        var anchor = document.createElement("A");
        anchor.className = "selectNodeOption";
        var text = document.createTextNode(nodes[node]);
        anchor.appendChild(text);
        li.appendChild(anchor);
        $("#nodesList").append(li);
    }
    // Add onClick event listener to each node
    $(".selectNodeOption").click(function() {
        var selectedNode = this.innerText;
        $("#nodeSelector").text(selectedNode);
        $("#takeThreadDumps").removeAttr("disabled");
        $("#takeHeapDumps").removeAttr("disabled");
        enableActionButton();
    });
}

function  performNodeRestart() {
    var stack_name = scrapePageForStackName();
    var url = [baseUrl, 'dorestartnode', region, stack_name, $("#nodeSelector").text(), $("#takeThreadDumps").is(':checked'), $("#takeHeapDumps").is(':checked')].join('/');
    send_http_get_request(url);
    redirectToLog(stack_name);
}