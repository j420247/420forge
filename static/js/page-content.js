var baseUrl = window.location .protocol + "//" + window.location.host;
var region = $("meta[name=region]").attr("value");
var action = window.location.pathname.substr(1);

function selectStack(stack_name) {
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

    $("#action-button").attr("aria-disabled", false);

    updateStats(stack_name);
}

function updateStats(stack_name, stack_region) {
    if (stack_name === 'actionreadytostart') return;
    if (! stack_region) stack_region = region;

    var serviceStatusRequest = new XMLHttpRequest();
    serviceStatusRequest.open("GET", baseUrl  + "/serviceStatus/" + stack_region + "/" + stack_name, true);
    serviceStatusRequest.setRequestHeader("Content-Type", "text/xml");
    serviceStatusRequest.onreadystatechange = function () {
        if (serviceStatusRequest.readyState === XMLHttpRequest.DONE && serviceStatusRequest.status === 200) {
            $("#serviceStatus").html("Service status: " + getStatusLozenge(serviceStatusRequest.responseText));
        }
    };

    if ($("#serviceStatus").find('span.aui-lozenge').length == 0)
        $("#serviceStatus").html("Service status: <aui-spinner size=\"small\" ></aui-spinner>");

    var stackStateRequest = new XMLHttpRequest();
    stackStateRequest.open("GET", baseUrl  + "/stackState/" + stack_region + "/" + stack_name, true);
    stackStateRequest.setRequestHeader("Content-Type", "text/xml");
    stackStateRequest.onreadystatechange = function () {
        if (stackStateRequest.readyState === XMLHttpRequest.DONE && stackStateRequest.status === 200) {
            $("#stackState").html("Stack status: " + getStatusLozenge(stackStateRequest.responseText));
            if (stackStateRequest.responseText.trim() === "\"CREATE_COMPLETE\"" ||
                stackStateRequest.responseText.trim() === "\"UPDATE_COMPLETE\"" ||
                stackStateRequest.responseText.trim() === "\"UPDATE_ROLLBACK_COMPLETE\"")
                // only request service status if stack actions are complete and successful
                serviceStatusRequest.send();
        }
    };
    if ($("#stackState").find('span.aui-lozenge').length == 0)
        $("#stackState").html("Stack status: <aui-spinner size=\"small\" ></aui-spinner>");
    stackStateRequest.send();

    var getStackActionInProgressRequest = new XMLHttpRequest();
    getStackActionInProgressRequest.open("GET", baseUrl + "/getActionInProgress/" + stack_region + "/" + stack_name, true);
    getStackActionInProgressRequest.setRequestHeader("Content-Type", "text/xml");
    getStackActionInProgressRequest.onreadystatechange = function () {
        if (getStackActionInProgressRequest.readyState === XMLHttpRequest.DONE && getStackActionInProgressRequest.status === 200) {
            var actionInProgress = JSON.parse(getStackActionInProgressRequest.responseText);
            $("#currentAction").html("Action in progress: " + getStatusLozenge(actionInProgress, "moved"));
            if (actionInProgress.toLowerCase() !== "none" && window.location.href.indexOf("/admin/") === -1) {
                $("#currentAction").append("&nbsp;<span class=\"aui-icon aui-icon-small aui-iconfont-unlock aui-button\" id=\"unlockIcon\">Unlock this stack</span>");
                document.getElementById("unlockIcon").addEventListener("click", function (data) {
                    window.location = baseUrl + "/admin/" + stack_name;
                });
            }
        }
    };
    getStackActionInProgressRequest.send();

    var getVersionRequest = new XMLHttpRequest();
    getVersionRequest.open("GET", baseUrl + "/getVersion/" + stack_region + "/" + stack_name, true);
    getVersionRequest.setRequestHeader("Content-Type", "text/xml");
    getVersionRequest.onreadystatechange = function () {
        if (getVersionRequest.readyState === XMLHttpRequest.DONE && getVersionRequest.status === 200) {
            var version = JSON.parse(getVersionRequest.responseText);
            $("#currentVersion").html("Current version: " + version);
        }
    };
    if ($("#currentVersion").html() && $("#currentVersion").html().length <= 17)
        $("#currentVersion").html("Current version: <aui-spinner size=\"small\" ></aui-spinner>");
    getVersionRequest.send();

    var getNodesRequest = new XMLHttpRequest();
    getNodesRequest.open("GET", baseUrl + "/getNodes/" + stack_region + "/" + stack_name, true);
    getNodesRequest.setRequestHeader("Content-Type", "text/xml");
    getNodesRequest.onreadystatechange = function () {
        if (getNodesRequest.readyState === XMLHttpRequest.DONE && getNodesRequest.status === 200) {
            $("#nodes").html("");
            var nodes = JSON.parse(getNodesRequest.responseText);
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
    if ($("#nodes").html() && $("#nodes").html().length <= 4)
        $("#nodes").html("<aui-spinner size=\"small\" ></aui-spinner>");
    getNodesRequest.send();
}

function getStatusLozenge(text, cssClass) {
    if (cssClass) {
        if (text.toLowerCase() === 'none') {
            cssClass = "success";
        }
    } else {
        var cssClass = "";
        text = text.trim();
        text = text.replace(/"/g, "");
        switch (text) {
            case "CREATE_COMPLETE":
            case "UPDATE_COMPLETE":
            case "RUNNING":
            case "FIRST_RUN":
            case "Valid":
            case "None":
                cssClass = "success";
                break;
            case "UPDATE_IN_PROGRESS":
            case "CREATE_IN_PROGRESS":
            case "DELETE_IN_PROGRESS":
                cssClass = "moved";
                break;
            case "Invalid":
            default:
                cssClass = "error";
        }
    }

    return "<span class=\"aui-lozenge aui-lozenge-" + cssClass + "\">" + text + "</span>"
}

function performAction() {
    var stack_name = scrapePageForStackName();
    var url = baseUrl + "/do" + action + "/" + region + "/" + stack_name;

    var actionRequest = new XMLHttpRequest();
    actionRequest.open("GET", url, true);
    actionRequest.setRequestHeader("Content-Type", "text/xml");
    actionRequest.addEventListener("load", processResponse);
    actionRequest.send();

    redirectToLog(stack_name);
}

document.addEventListener('DOMContentLoaded', function() {
    $("#stackInformation").hide();
    onReady();
    checkAuthenticated();
}, false);
