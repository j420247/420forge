
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

    if (action == "upgrade") {
        document.getElementById("versionCheckButton").addEventListener("click", function (data) {
            version = $("#upgradeVersionSelector").val();
            var url = 'https://s3.amazonaws.com/atlassian-software/releases/confluence/atlassian-confluence-' + version + '-linux-x64.bin';
            $.ajax({
                url: url,
                headers: {'Access-Control-Allow-Origin': url},
                type: 'HEAD',
                complete: function (xhr) {
                    switch (xhr.status) {
                        case 200:
                            $("#versionExists").html(getStatusLozenge("Valid"));
                            break;
                        default:
                            $("#action-button").attr("aria-disabled", false);
                            $("#versionExists").html(getStatusLozenge("Valid"));
                            $("#upgradeVersionSelector").text(version);
                    }
                }
            });
        });
    }

    //     makeCorsRequest('https://s3.amazonaws.com/atlassian-software/releases/confluence/atlassian-confluence-' + version + '-linux-x64.bin',
    //         function(xhr) {
    //             switch (xhr.statusText) {
    //                 case "success":
    //                     break;
    //                 case "error":
    //                 default:
    //                     $("#versionExists").html(getStatusLozenge(stackState.responseText))
    //             }
    //         });
    //     $("#upgradeVersionSelector").text(version);
    //     $("#upgrade-button").attr("aria-disabled", false);
    // }, false);

    var actionButton = document.getElementById("action-button");
    actionButton.addEventListener("click", function (data) {
        // $("#log").setAttribute("src", "status/" + stackName);
        $("#log").css("background", "rgba(0,20,70,.08)");
        performAction(action, env, stackName)
    });
});

function performAction(action, env, stackName) {
    var baseUrl = window.location .protocol + "//" + window.location.host;
    var env = $("meta[name=env]").attr("value");
    var action = $("meta[name=action]").attr("value");

    var actionRequest = new XMLHttpRequest();
    // actionRequest.open("GET", baseUrl  + "/" + action + "/" + env + "/" + stackName, true); //TODO re-enable
    actionRequest.open("GET", baseUrl  + "/status/" + stackName, true);
    actionRequest.setRequestHeader("Content-Type", "text/xml");
    actionRequest.onreadystatechange = function () {
        if (actionRequest.readyState === 4 && actionRequest.status === 200) {
            $("#log").contents().find('body').html(actionRequest.responseText);
        }
    };
    actionRequest.send();
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
        default:
            cssClass = "error";
    }

    return "<span class=\"aui-lozenge aui-lozenge-" + cssClass + "\">" + text + "</span>"
}


// Create the XHR object.
function createCORSRequest(method, url) {
    var xhr = new XMLHttpRequest();
    if ("withCredentials" in xhr) {
        // XHR for Chrome/Firefox/Opera/Safari.
        xhr.open(method, url, true);
    } else if (typeof XDomainRequest != "undefined") {
        // XDomainRequest for IE.
        xhr = new XDomainRequest();
        xhr.open(method, url);
    } else {
        // CORS not supported.
        xhr = null;
    }
    return xhr;
}

// Helper method to parse the title tag from the response.
function getTitle(text) {
    return text.match('<title>(.*)?</title>')[1];
}

// Make the actual CORS request.
function makeCorsRequest(url, callback) {

    var xhr = createCORSRequest('HEAD', url);
    if (!xhr) {
        alert('CORS not supported');
        return;
    }

    // Response handlers.
    xhr.onload = function () {
        var text = xhr.responseText;
        var title = getTitle(text);
    };

    xhr.send();
}

function removeElementsByClass(className){
    var elements = document.getElementsByClassName(className);
    while(elements.length > 0){
        elements[0].parentNode.removeChild(elements[0]);
    }
}