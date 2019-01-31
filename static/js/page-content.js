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

    updateStackInfo(stack_name);
}

function updateStackInfo(stack_name, stack_region) {
    if (stack_name === 'actionreadytostart') return;
    if (! stack_region) stack_region = region;

    // show spinners if no content
    if ($("#serviceStatus").find('span.aui-lozenge').length == 0)
        $("#serviceStatus").html("Service status: <aui-spinner size=\"small\" ></aui-spinner>");
    if ($("#stackState").find('span.aui-lozenge').length == 0)
        $("#stackState").html("Stack status: <aui-spinner size=\"small\" ></aui-spinner>");
    if ($("#currentVersion").length && $("#currentVersion").html().length <= 17)
        $("#currentVersion").html("Current version: <aui-spinner size=\"small\" ></aui-spinner>");
    if ($("#nodes").length && $("#nodes").html().length <= 4)
        $("#nodes").html("<aui-spinner size=\"small\" ></aui-spinner>");

    var functionParams = {
        stack_name: stack_name,
        stack_region: stack_region
    };

    // request stack info
    send_http_get_request(baseUrl  + "/stackState/" + stack_region + "/" + stack_name, displayStackStateAndRequestServiceStatus, functionParams);
    send_http_get_request(baseUrl + "/getActionInProgress/" + stack_region + "/" + stack_name, displayActionInProgress);
    send_http_get_request(baseUrl + "/getVersion/" + stack_region + "/" + stack_name, displayVersion);
    send_http_get_request(baseUrl + "/getNodes/" + stack_region + "/" + stack_name, displayNodes);
}

function displayStackStateAndRequestServiceStatus(responseText, functionParams) {
    $("#stackState").html("Stack status: " + getStatusLozenge(responseText));
    if (responseText.trim() === "\"CREATE_COMPLETE\"" ||
        responseText.trim() === "\"UPDATE_COMPLETE\"" ||
        responseText.trim() === "\"UPDATE_ROLLBACK_COMPLETE\"")
        // only request service status if stack actions are complete and successful
        send_http_get_request(baseUrl  + "/serviceStatus/" + functionParams.stack_region + "/" + functionParams.stack_name, displayServiceStatus);
    else
        $("#serviceStatus").html("Service status: ");
}

function displayServiceStatus(responseText) {
    $("#serviceStatus").html("Service status: " + getStatusLozenge(responseText));
}

function displayActionInProgress(responseText) {
    var actionInProgress = JSON.parse(responseText);
    $("#currentAction").html("Action in progress: " + getStatusLozenge(actionInProgress, "moved"));
    if (actionInProgress.toLowerCase() !== "none" && window.location.href.indexOf("/admin/") === -1) {
        $("#currentAction").append("&nbsp;<span class=\"aui-icon aui-icon-small aui-iconfont-unlock aui-button\" id=\"unlockIcon\">Unlock this stack</span>");
        document.getElementById("unlockIcon").addEventListener("click", function (data) {
            window.location = baseUrl + "/admin/" + stack_name;
        });
    }
}

function displayVersion(responseText) {
    var version = JSON.parse(responseText);
    $("#currentVersion").html("Current version: " + version);
}

function displayNodes(responseText) {
    $("#nodes").html("");
    var nodes = JSON.parse(responseText);
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
    send_http_get_request(baseUrl + "/do" + action + "/" + region + "/" + stack_name);
    redirectToLog(stack_name);
}

function onReady() {
    // empty function for errors, overridden by each action
}
document.addEventListener('DOMContentLoaded', function() {
    $("#stackInformation").hide();
    onReady();
    checkAuthenticated();
}, false);
