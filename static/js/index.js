
$(document).ready(function() {
    $("#stackInformation").hide();
    var stacks = document.getElementsByClassName("selectStackOption");
    var stackName = "none";
    var version = "none";
    for (var i = 0; i < stacks.length; i ++) {
        stacks[i].addEventListener("click", function (data) {
            stackName = data.target.text;
            $("#stackSelector").text(stackName);
            $("#stackName").text(stackName);
            $("#pleaseSelectStackMsg").hide();
            $("#stackInformation").show();
            if (document.getElementById("upgradeVersionSelector")) {
                $("#upgradeVersionSelector").attr("aria-disabled", false);
            } else {
                $("#action-button").attr("aria-disabled", false);
            }
            updateStats(stackName);
        }, false);
    }

    var versions = document.getElementsByClassName("selectVersionOption");
    for (var i = 0; i < versions.length; i ++) {
        versions[i].addEventListener("click", function (data) {
            version = data.target.text;
            $("#upgradeVersionSelector").text(version);
            $("#action-button").attr("aria-disabled", false);
        }, false);
    }

    var actionButton = document.getElementById("action-button");
    actionButton.addEventListener("click", function (data) {
        $("#log").setAttribute("src", "status/" + stackName);
        $("#log").css("background", "rgba(0,20,70,.08)");
    })
});

function updateStats(stackName) {
    var baseUrl = window.location .protocol + "//" + window.location.host;
    var env = $("meta[name=env]").attr("value");

    removeElementsByClass("aui-lozenge");

    var stackState = new XMLHttpRequest();
    stackState.open("GET", baseUrl  + "/stackState/" + env + "/" + stackName, true);
    stackState.setRequestHeader("Content-Type", "text/xml");
    stackState.onreadystatechange = function () {
        if (stackState.readyState === 4 && stackState.status === 200) {
            $("#stackState").append(getStatusLozenge(stackState.responseText));
        }
    };
    stackState.send();

    var serviceStatus = new XMLHttpRequest();
    serviceStatus.open("GET", baseUrl  + "/serviceStatus/" + env + "/" + stackName, true);
    serviceStatus.setRequestHeader("Content-Type", "text/xml");
    serviceStatus.onreadystatechange = function () {
        if (serviceStatus.readyState === 4 && serviceStatus.status === 200) {
            $("#serviceStatus").append(getStatusLozenge(serviceStatus.responseText));
        }
    };
    serviceStatus.send();
}

function getStatusLozenge(text) {
    var cssClass = "";
    text = text.trim();
    text = text.replace(/"/g, "")
    switch (text) {
        case "UPDATE_COMPLETE":
        case "RUNNING":
            cssClass = "success";
            break;
        case "UPDATE_IN_PROGRESS":
            cssClass = "moved";
            break;
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