function onReady() {
    var stacks = document.getElementsByClassName("selectStackOption");
    for (var i = 0; i < stacks.length; i++) {
        stacks[i].addEventListener("click", function (data) {
            var stack_name = data.target.text;
            selectStack(stack_name);
            $("#nodesList").empty();
            $("#nodeSelector")[0].text = "Select Node";
            $("#cpuChartDiv").empty();
            $("#cpuChartDiv").append("<canvas id='cpuChart' hidden>");
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
        $("#cpuChartDiv").empty();
        $("#cpuChartDiv").append("<canvas id='cpuChart' class='cpuChartEmpty' hidden>");
        drawChart([],[], '');
        getNodeCPU(this.innerText);
        enableActionButton();
    });
}

function getNodeCPU(node) {
    var stack_name = scrapePageForStackName();
    var url = [baseUrl, 'getNodeCPU', region, stack_name, node].join('/');
    send_http_get_request(url, displayNodeCPU);
}

function drawChart(timestamps_sorted, cpu_sorted, border_color) {
    var ctx = document.getElementById('cpuChart').getContext('2d');
    new Chart(ctx, {
        type: 'line',
        data: {
            labels: timestamps_sorted,
            datasets: [{
                label: 'CPU Utilization over the last 30 minutes',
                borderColor: border_color,
                data: cpu_sorted
            }]
        },
        options: {
            scales: {
                yAxes: [{
                    ticks: {
                        suggestedMin: 0,
                        suggestedMax: 100
                    }
                }]
            }
        }
    });
}

function displayNodeCPU(responseText) {
    var cpu_data_dict = JSON.parse(responseText);
    var timestamps = Object.keys(cpu_data_dict);
    timestamps.sort();
    var timestamps_sorted = [];
    var cpu_sorted = [];
    for (var i = 0; i < timestamps.length; i++) {
        var date = new Date(parseInt(timestamps[i]) * 1000);
        var month = date.getMonth() + 1;
        var day_num = date.getDate().toString().length === 1 ? "0" + date.getDate() : date.getDate();
        var hours = date.getHours().toString().length === 1 ? "0" + date.getHours() : date.getHours();
        var minutes = date.getMinutes().toString().length === 1 ? "0" + date.getMinutes() : date.getMinutes();
        timestamps_sorted.push(month + "/" + (day_num) + " " + hours + ":" + minutes);
        cpu_sorted.push(cpu_data_dict[timestamps[i]]);
    }

    var border_color = '#00875A';
    for (var i = cpu_sorted.length - 6; i < cpu_sorted.length; i++) {
        if (cpu_sorted[i] > 80) {
            border_color = '#DE3505';
            break;
        }
    }
    drawChart(timestamps_sorted, cpu_sorted, border_color);
    $("#cpuChart").removeClass("cpuChartEmpty");
    $("#cpuChart").removeAttr("hidden");
}

function  performNodeRestart() {
    var stack_name = scrapePageForStackName();
    var url = [baseUrl, 'dorestartnode', region, stack_name, $("#nodeSelector").text(), $("#takeThreadDumps").is(':checked'), $("#takeHeapDumps").is(':checked')].join('/');
    send_http_get_request(url);
    redirectToLog(stack_name);
}