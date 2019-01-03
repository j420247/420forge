var baseUrl = window.location .protocol + "//" + window.location.host;
var region = $("meta[name=region]").attr("value");
var action = window.location.pathname.substr(1);

function onReady() {
    var stacks = document.getElementsByClassName("selectStackOption");
    for (var i = 0; i < stacks.length; i++) {
        stacks[i].addEventListener("click", function (data) {
            selectStack(data.target.text);
        }, false);
    }

    if (action.indexOf("/") != -1)
        action = action.substr(action.indexOf("/") + 1);

    // Version checking not currently working (and only worked for Confluence in the past). Leaving so we can fix for public.
    // if (action === "upgrade") {
    //     document.getElementById("versionCheckButton").addEventListener("click", function (data) {
    //         var version = $("#upgradeVersionSelector").val();
    //         var url = 'https://s3.amazonaws.com/atlassian-software/releases/confluence/atlassian-confluence-' + version + '-linux-x64.bin';
    //         $.ajax({
    //             url: url,
    //             type: 'HEAD',
    //             headers: {'Access-Control-Allow-Origin': url},
    //             complete: function (xhr) {
    //                 switch (xhr.status) {
    //                     case 200:
    //                         $("#versionExists").html(getStatusLozenge("Valid"));
    //                         $("#action-button").attr("aria-disabled", false);
    //                         break;
    //                     case 403:
    //                     default:
    //                         $("#versionExists").html(getStatusLozenge("Invalid"));
    //                 }
    //             },
    //         });
    //     });
    // }

    addDefaultActionButtonListener();
}

function addDefaultActionButtonListener() {
    var actionButton = document.getElementById("action-button");
    if (actionButton)
        actionButton.addEventListener("click", defaultActionBtnEvent);
}

var defaultActionBtnEvent = function() {
    if (action === 'upgrade') {
        performAction($("#upgradeVersionSelector").val())
    } else {
        performAction()
    }
};

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

    updateStats(stack_name);

    // Enable extra input parameters per action
    switch (action) {
        case "upgrade":
            $("#upgradeVersionSelector").removeAttr("disabled");
            $("#action-button").attr("aria-disabled", false);

            // Version checking not currently working
            // currently only works for Confluence
            // $("#versionCheckButton").removeAttr("disabled");
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
                .split('\\n').join('<br />')
                .split('"').join('')
                .trim());

            $("#log").contents().find('body').scrollTop(9999999999);
        }
    };
    statusRequest.send();
}

function processResponse() {
    if (this.status !== 200) {
        window.location = baseUrl + "/error/" + this.status;
    }
}

function performAction(version) {
    // scrape page for stack_name
    var stack_name = $("#stackName").text();
    if (! stack_name) {
        stack_name = $("#StackNameVal").val();
    }

    var url = baseUrl + "/do" + action + "/" + region + "/" + stack_name;

    var actionRequest = new XMLHttpRequest();
    switch (action) {
        case "upgrade":
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
        window.location = baseUrl + "/actionprogress/" + action + "?stack=" + stack_name;
    }, 1000);
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
            if (!$("#currentAction").children().hasClass("aui-lozenge")) {
                $("#currentAction").html("Action in progress: " + getStatusLozenge(actionInProgress, "moved"));
                if (actionInProgress.toLowerCase() !== "none" && window.location.href.indexOf("/admin/") === -1) {
                    $("#currentAction").append("&nbsp;<span class=\"aui-icon aui-icon-small aui-iconfont-unlock aui-button\" id=\"unlockIcon\">Unlock this stack</span>");
                    document.getElementById("unlockIcon").addEventListener("click", function (data) {
                        window.location = baseUrl + "/admin/" + stack_name;
                    });
                }
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

function removeElementsByClass(className){
    var elements = document.getElementsByClassName(className);
    while(elements.length > 0){
        elements[0].parentNode.removeChild(elements[0]);
    }
}

document.addEventListener('DOMContentLoaded', function() {
    $("#stackInformation").hide();
    onReady();
    checkAuthenticated();
}, false);
