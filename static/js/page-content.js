
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
            $("#stackSelector").text(stackName);
            $("#stackName").text(stackName);
            $("#pleaseSelectStackMsg").hide();
            $("#stackInformation").show();

            if (action == "upgrade") {
                $("#upgradeVersionSelector").removeAttr("disabled");
                $("#versionCheckButton").removeAttr("disabled");
            } else {
                $("#action-button").attr("aria-disabled", false);
            }
            updateStats(stackName);
        }, false);
    }

    if (action === "upgrade") {
        document.getElementById("versionCheckButton").addEventListener("click", function (data) {
            version = $("#upgradeVersionSelector").val();
            var url = 'https://s3.amazonaws.com/atlassian-software/releases/confluence/atlassian-confluence-' + version + '-linux-x64.bin';
            $.ajax({
                url: url,
                type: 'HEAD',
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
    actionButton.addEventListener("click", function (data) {
        // $("#log").setAttribute("src", "status/" + stackName);
        $("#log").css("background", "rgba(0,20,70,.08)");
        performAction(action, env, stackName, version)
    });
});

function performAction(action, env, stackName, version) {
    var baseUrl = window.location .protocol + "//" + window.location.host;
    var env = $("meta[name=env]").attr("value");
    var action = $("meta[name=action]").attr("value");
    var url = baseUrl  + "/" + action + "/" + env + "/" + stackName;

    var actionRequest = new XMLHttpRequest();
    if (action === "upgrade") {
        url += "/" + version;
    }

    actionRequest.open("GET", url, true);
    actionRequest.setRequestHeader("Content-Type", "text/xml");
    actionRequest.send();

    var statusRequest = new XMLHttpRequest();
    statusRequest.open("GET", baseUrl  + "/status/" + stackName, true);
    statusRequest.setRequestHeader("Content-Type", "text/xml");
    statusRequest.onreadystatechange = function () {
        $("#log").contents().find('body').html(statusRequest.responseText);
    };
    // wait a few seconds to get more initial logging
    setTimeout(function() {
        statusRequest.send();
    }, 2000);
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
        if (stackStateRequest.readyState === 4 && stackStateRequest.status === 200) {
            $("#stackState").html("Stack State: " + getStatusLozenge(stackStateRequest.responseText));
        }
    };
    stackStateRequest.send();

    var serviceStatusRequest = new XMLHttpRequest();
    serviceStatusRequest.open("GET", baseUrl  + "/serviceStatus/" + env + "/" + stackName, true);
    serviceStatusRequest.setRequestHeader("Content-Type", "text/xml");
    $("#serviceStatus").html("Service Status: ");
    serviceStatusRequest.onreadystatechange = function () {
        if (serviceStatusRequest.readyState === 4 && serviceStatusRequest.status === 200) {
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