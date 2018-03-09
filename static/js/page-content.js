
$(document).ready(function() {
    $("#stackInformation").hide();
    var stacks = document.getElementsByClassName("selectStackOption");
    var stackName = "none";
    var version = "none";
    var env = $("meta[name=env]").attr("value");
    var action = $("meta[name=action]").attr("value");

    for (var i = 0; i < stacks.length; i ++) {
        stacks[i].addEventListener("click", function (data) {
            stackName = data.target.text;
            selectStack(stackName, action);
        }, false);
    }

    // currently only works for Confluence
    if (action === "upgrade" && stackName.indexOf("eac") !== -1 && stackName.indexOf("eacj") === -1) {
        document.getElementById("versionCheckButton").addEventListener("click", function (data) {
            version = $("#upgradeVersionSelector").val();
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

    addRefreshListener(stackName);

    var actionButton = document.getElementById("action-button");
    actionButton.addEventListener("click", function (data) {
        if (action === "upgrade" && version === 'none')
            version = $("#upgradeVersionSelector").val();
        performAction(action, env, stackName, version)
    });
});

function selectStack(stackName, action) {
    $("#stackSelector").text(stackName);
    $("#stackName").text(stackName);
    $("#pleaseSelectStackMsg").hide();
    $("#stackInformation").show();

    if (action == "upgrade") {
        $("#upgradeVersionSelector").removeAttr("disabled");
        $("#action-button").attr("aria-disabled", false);

        // currently only works for Confluence
        if (stackName.indexOf("eac") !== -1 && stackName.indexOf("eacj") === -1)
            $("#versionCheckButton").removeAttr("disabled");
    } else {
        $("#versionCheckButton").hide();
        $("#action-button").attr("aria-disabled", false);
    }
    updateStats(stackName);
}

function addRefreshListener(stackName) {
    var refreshButton = document.getElementById("refresh-status");
    refreshButton.addEventListener("click", function (data) {
        refreshButton.classList.remove("aui-iconfont-refresh");
        refreshButton.classList.add("aui-icon-wait");
        getStatus(stackName, null)
        refreshButton.classList.remove("aui-icon-wait");
        refreshButton.classList.add("aui-iconfont-refresh");
    });
}

function getStatus(stackName) {
    $("#log").css("background", "rgba(0,20,70,.08)");

    var baseUrl = window.location .protocol + "//" + window.location.host;
    var statusRequest = new XMLHttpRequest();
    statusRequest.open("GET", baseUrl + "/status/" + stackName, true);
    statusRequest.setRequestHeader("Content-Type", "text/xml");
    statusRequest.onreadystatechange = function () {
        if (statusRequest.readyState === XMLHttpRequest.DONE && statusRequest.status === 200) {
            $("#log").css("background", "rgba(0,0,0,0)");
            $("#log").contents().find('body').html(statusRequest.responseText
                .substr(1, statusRequest.responseText.length - 3)
                .split('",').join('<br />')
                .split('"').join('')
                .trim());
        }
    };
    statusRequest.send();
}

function performAction(action, env, stackName, version) {
    if (window.confirm('Are you sure? These buttons are connected now so your action will fire.')) {
        var baseUrl = window.location.protocol + "//" + window.location.host;
        var env = $("meta[name=env]").attr("value");
        var action = $("meta[name=action]").attr("value");
        var url = baseUrl + "/" + action + "/" + env + "/" + stackName;

        var actionRequest = new XMLHttpRequest();
        if (action === "upgrade") {
            url += "/" + version;
        }

        actionRequest.open("GET", url, true);
        actionRequest.setRequestHeader("Content-Type", "text/xml");
        actionRequest.send();

        // Redirect to action progress screen
        window.location = baseUrl + "/actionprogress/" + action + "/" + stackName;
    }
}

function updateStats(stackName) {
    var baseUrl = window.location .protocol + "//" + window.location.host;
    var env = $("meta[name=env]").attr("value");

    removeElementsByClass("aui-lozenge");

    var stackStateRequest = new XMLHttpRequest();
    stackStateRequest.open("GET", baseUrl  + "/stackState/" + env + "/" + stackName, true);
    stackStateRequest.setRequestHeader("Content-Type", "text/xml");
    $("#stackState").html("Stack State: ");
    stackStateRequest.onreadystatechange = function () {
        if (stackStateRequest.readyState === XMLHttpRequest.DONE && stackStateRequest.status === 200) {
            $("#stackState").html("Stack State: " + getStatusLozenge(stackStateRequest.responseText));
        }
    };
    stackStateRequest.send();

    var serviceStatusRequest = new XMLHttpRequest();
    serviceStatusRequest.open("GET", baseUrl  + "/serviceStatus/" + env + "/" + stackName, true);
    serviceStatusRequest.setRequestHeader("Content-Type", "text/xml");
    $("#serviceStatus").html("Service Status: ");
    serviceStatusRequest.onreadystatechange = function () {
        if (serviceStatusRequest.readyState === XMLHttpRequest.DONE && serviceStatusRequest.status === 200) {
            $("#serviceStatus").html("Service Status: " + getStatusLozenge(serviceStatusRequest.responseText));
        }
    };
    serviceStatusRequest.send();
}

function getStatusLozenge(text) {
    var cssClass = "";
    text = text.trim();
    text = text.replace(/"/g, "")
    switch (text) {
        case "CREATE_COMPLETE":
        case "UPDATE_COMPLETE":
        case "RUNNING":
        case "Valid":
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