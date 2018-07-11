var baseUrl = window.location .protocol + "//" + window.location.host;
var region = $("meta[name=region]").attr("value");
var action = $("meta[name=action]").attr("value");
var stackName = $("meta[name=stack_name]").attr("value");
var version = $("meta[name=version]").attr("value");

function onReady() {
    var stacks = document.getElementsByClassName("selectStackOption");
    for (var i = 0; i < stacks.length; i++) {
        stacks[i].addEventListener("click", function (data) {
            selectStack(data.target.text);
        }, false);
    }

    // currently only works for Confluence
    if (action === "upgrade" && stackName.indexOf("eac") !== -1 && stackName.indexOf("eacj") === -1) {
        document.getElementById("versionCheckButton").addEventListener("click", function (data) {
            var version = $("#upgradeVersionSelector").val();
            $('meta[name=version]').attr('value', version);
            var url = 'https://s3.amazonaws.com/atlassian-software/releases/confluence/atlassian-confluence-' + version + '-linux-x64.bin';
            $.ajax({
                url: url,
                type: 'HEAD',
                headers: {'Access-Control-Allow-Origin': url},
                complete: function (xhr) {
                    switch (xhr.status) {
                        case 200:
                            $("#versionExists").html(getStatusLozenge("Valid"));
                            $("#action-button").attr("aria-disabled", false);
                            break;
                        case 403:
                        default:
                            $("#versionExists").html(getStatusLozenge("Invalid"));
                    }
                },
            });
        });
    }

    var actionButton = document.getElementById("action-button");
    if (actionButton)
        actionButton.addEventListener("click", defaultActionBtnEvent);
}

var defaultActionBtnEvent = function() {
    if (action === 'upgrade') {
        version = $("#upgradeVersionSelector").val();
        $('meta[name=version]').attr('value', version);
    }
    performAction()
};

function selectStack(stack_name) {
    $('meta[name=stack_name]').attr('value', stack_name);
    $("#stackSelector").text(stack_name);
    $("#stackName").text(stack_name);
    $("#pleaseSelectStackMsg").hide();
    $("#stackInformation").show();

    // clean up stack info
    removeElementsByClass("aui-lozenge");
    $("#serviceStatus").html("Service status: ");
    $("#stackState").html("Stack status: ");
    $("#currentAction").html("Action in progress: ");
    $("#currentVersion").html("Current version: ");
    $("#nodes").html("");

    updateStats(stack_name);

    // Enable extra input parameters per action
    switch (action) {
        case "upgrade":
            $("#upgradeVersionSelector").removeAttr("disabled");
            $("#action-button").attr("aria-disabled", false);

            // currently only works for Confluence
            if (stack_name.indexOf("eac") !== -1 && stack_name.indexOf("eacj") === -1)
                $("#versionCheckButton").removeAttr("disabled");
            break;
        case "update":
        case "clone":
            $("#versionCheckButton").hide();
            break;
        case "admin":
            $("#action-button").attr("aria-disabled", true);
            break;
        case "rollingrestart":
        case "fullrestart":
            $("#takeThreadDumps").removeAttr("disabled");
            $("#takeHeapDumps").removeAttr("disabled");
        default:
            $("#versionCheckButton").hide();
            $("#action-button").attr("aria-disabled", false);
    }
}

function getStatus(stack_name) {
    if (stack_name === 'actionreadytostart') return;

    $("#log").css("background", "rgba(0,20,70,.08)");

    var statusRequest = new XMLHttpRequest();
    statusRequest.open("GET", baseUrl + "/status/" + stack_name, true);
    statusRequest.setRequestHeader("Content-Type", "text/xml");
    statusRequest.onreadystatechange = function () {
        if (statusRequest.readyState === XMLHttpRequest.DONE && statusRequest.status === 200) {
            $("#log").css("background", "rgba(0,0,0,0)");

            // If getting the logs has blipped, don't overwrite legitimate logging
            if ((countOccurences($("#log").contents().text(), "No current status for") !== 1 &&
                    countOccurences($("#log").contents().text(), "Waiting for logs") !== 1)
                    &&
                (countOccurences(statusRequest.responseText, "No current status for") === 1 ||
                countOccurences(statusRequest.responseText, "Waiting for logs") === 1))
            return;

            $("#log").contents().find('body').html(statusRequest.responseText
                .substr(1, statusRequest.responseText.length - 3)
                .split('",').join('<br />')
                .split('"').join('')
                .trim());
        }
    };
    statusRequest.send();
}

function processResponse() {
    if (this.status !== 200) {
        window.location = baseUrl + "/error/" + this.status;
    }
}

function performAction() {
    stackName = $("meta[name=stack_name]").attr("value");
    var url = baseUrl + "/do" + action + "/" + region + "/" + stackName;

    var actionRequest = new XMLHttpRequest();
    switch (action) {
        case "upgrade":
            version = $("meta[name=version]").attr("value");
            url += "/" + version;
            break;
        case "rollingrestart":
        case "fullrestart":
            url += "/" + document.getElementById("takeThreadDumps").checked
                + "/" + document.getElementById("takeHeapDumps").checked
    }

    actionRequest.open("GET", url, true);
    actionRequest.setRequestHeader("Content-Type", "text/xml");
    actionRequest.addEventListener("load", processResponse);
    actionRequest.send();

    // Wait a mo for action to begin  in backend
    setTimeout(function () {
        // Redirect to action progress screen
        window.location = baseUrl + "/actionprogress/" + action + "/" + stackName;
    }, 1000);
}

function updateStats(stack_name) {
    if (stack_name === 'actionreadytostart') return;

    removeElementsByClass("aui-lozenge");

    var serviceStatusRequest = new XMLHttpRequest();
    serviceStatusRequest.open("GET", baseUrl  + "/serviceStatus/" + region + "/" + stack_name, true);
    serviceStatusRequest.setRequestHeader("Content-Type", "text/xml");
    serviceStatusRequest.onreadystatechange = function () {
        if (serviceStatusRequest.readyState === XMLHttpRequest.DONE && serviceStatusRequest.status === 200) {
            $("#serviceStatus").html("Service status: " + getStatusLozenge(serviceStatusRequest.responseText));
        }
    };
    $("#serviceStatus").html("Service status: <span class=\"button-spinner\" style=\"display: inline-block; height: 10px; width: 20px\"></span>");
    AJS.$('.button-spinner').spin();

    var stackStateRequest = new XMLHttpRequest();
    stackStateRequest.open("GET", baseUrl  + "/stackState/" + region + "/" + stack_name, true);
    stackStateRequest.setRequestHeader("Content-Type", "text/xml");
    stackStateRequest.onreadystatechange = function () {
        if (stackStateRequest.readyState === XMLHttpRequest.DONE && stackStateRequest.status === 200) {
            if (!$("#stackState").children().hasClass("aui-lozenge"))
                $("#stackState").append(getStatusLozenge(stackStateRequest.responseText));
            if (stackStateRequest.responseText.trim() === "\"CREATE_COMPLETE\"" ||
                stackStateRequest.responseText.trim() === "\"UPDATE_COMPLETE\"")
                // only request service status if stack actions are complete and successful
                serviceStatusRequest.send();
        }
    };
    stackStateRequest.send();

    var getStackActionInProgressRequest = new XMLHttpRequest();
    getStackActionInProgressRequest.open("GET", baseUrl + "/getActionInProgress/" + region + "/" + stack_name, true);
    getStackActionInProgressRequest.setRequestHeader("Content-Type", "text/xml");
    getStackActionInProgressRequest.onreadystatechange = function () {
        if (getStackActionInProgressRequest.readyState === XMLHttpRequest.DONE && getStackActionInProgressRequest.status === 200) {
            if (!$("#currentAction").children().hasClass("aui-lozenge"))
                $("#currentAction").append(getStatusLozenge(getStackActionInProgressRequest.responseText));
        }
    };
    getStackActionInProgressRequest.send();

    var getVersionRequest = new XMLHttpRequest();
    getVersionRequest.open("GET", baseUrl + "/getVersion/" + region + "/" + stack_name, true);
    getVersionRequest.setRequestHeader("Content-Type", "text/xml");
    getVersionRequest.onreadystatechange = function () {
        if (getVersionRequest.readyState === XMLHttpRequest.DONE && getVersionRequest.status === 200) {
            var version = JSON.parse(getVersionRequest.responseText);
            $("#currentVersion").html("Current version: " + version);
        }
    };
    getVersionRequest.send();

    var getNodesRequest = new XMLHttpRequest();
    getNodesRequest.open("GET", baseUrl + "/getNodes/" + region + "/" + stack_name, true);
    getNodesRequest.setRequestHeader("Content-Type", "text/xml");
    getNodesRequest.onreadystatechange = function () {
        if (getNodesRequest.readyState === XMLHttpRequest.DONE && getNodesRequest.status === 200) {
            var nodes = JSON.parse(getNodesRequest.responseText);
            $("#nodes").html("");
            if (!nodes[0]) {
                $("#nodes").html("None");
                return;
            }
            for (var node in nodes) {
                $("#nodes").append(nodes[node].ip + ": " + getStatusLozenge(nodes[node].status));
                if (node < nodes.length)
                    $("#nodes").append("<br>");
            }
        }
    };
    $("#nodes").html("<span class=\"button-spinner\" style=\"display: inline-block; height: 10px; width: 20px\"></span>");
    AJS.$('.button-spinner').spin();
    getNodesRequest.send();
}

function getStatusLozenge(text) {
    var cssClass = "";
    text = text.trim();
    text = text.replace(/"/g, "");
    switch (text) {
        case "CREATE_COMPLETE":
        case "UPDATE_COMPLETE":
        case "RUNNING":
        case "Valid":
        case "None":
            cssClass = "success";
            break;
        case "UPDATE_IN_PROGRESS":
            cssClass = "moved";
            break;
        case "Invalid":
        default:
            cssClass = "error";
    }

    return "<span class=\"aui-lozenge aui-lozenge-" + cssClass + "\">" + text + "</span>"
}

function removeElementsByClass(className){
    var elements = document.getElementsByClassName(className);
    while(elements.length > 0){
        elements[0].parentNode.removeChild(elements[0]);
    }
}

document.addEventListener('DOMContentLoaded', function() {
    $("#stackInformation").hide();
    onReady();
}, false);