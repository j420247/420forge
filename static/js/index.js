
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

            $("#upgradeVersionSelector").removeAttr("disabled");
            $("#versionCheckButton").removeAttr("disabled");
            updateStats(stackName);
        }, false);
    }

    document.getElementById("versionCheckButton").addEventListener("click", function (data) {
        version = $("#upgradeVersionSelector").val();
        var url = 'https://s3.amazonaws.com/atlassian-software/releases/confluence/atlassian-confluence-' + version + '-linux-x64.bin';
        $.ajax({
            url: url,
            headers: {  'Access-Control-Allow-Origin': url },
            type: 'HEAD',
            complete: function(xhr) {
                switch (xhr.status) {
                    case 200:
                        $("#versionExists").html(getStatusLozenge("Valid"));
                        break;
                    default:
                        $("#upgrade-button").attr("aria-disabled", false);
                        $("#versionExists").html(getStatusLozenge("Valid"));
                        $("#upgradeVersionSelector").text(version);
                }
            }
        });
    });

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
        $("#log").setAttribute("src", "status/" + stackName);
        $("#log").css("background", "rgba(0,20,70,.08)");
    });
});

function updateStats(stackName) {
    var baseUrl = window.location .protocol + "//" + window.location.host;
    var env = $("meta[name=env]").attr("value");

    removeElementsByClass("aui-lozenge");

    var stackState = new XMLHttpRequest();
    stackState.open("GET", baseUrl  + "/stackState/" + env + "/" + stackName, true);
    stackState.setRequestHeader("Content-Type", "text/xml");
    $("#stackState").html("Stack State: ");
    stackState.onreadystatechange = function () {
        if (stackState.readyState === 4 && stackState.status === 200) {
            $("#stackState").html("Stack State: " + getStatusLozenge(stackState.responseText));
        }
    };
    stackState.send();

    var serviceStatus = new XMLHttpRequest();
    serviceStatus.open("GET", baseUrl  + "/serviceStatus/" + env + "/" + stackName, true);
    serviceStatus.setRequestHeader("Content-Type", "text/xml");
    $("#serviceStatus").html("Service Status: ");
    serviceStatus.onreadystatechange = function () {
        if (serviceStatus.readyState === 4 && serviceStatus.status === 200) {
            $("#serviceStatus").html("Service Status: " + getStatusLozenge(serviceStatus.responseText));
        }
    };
    serviceStatus.send();
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