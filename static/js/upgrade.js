function onReady() {
    var stacks = document.getElementsByClassName("selectStackOption");
    for (var i = 0; i < stacks.length; i++) {
        stacks[i].addEventListener("click", function (data) {
            var stack_name = data.target.text;
            selectStack(stack_name);
            checkZDUCompatibility(stack_name);
            $("#upgradeVersionSelector").removeAttr("disabled");
        }, false);
    }
    $("#action-button").on("click", beginUpgrade);

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
}

function checkZDUCompatibility(stack_name) {
    $("#zduCheckDiv").removeAttr("style");
    $("#zduCheckLbl").text("Checking Zero Downtime Upgrade compatibility ...");
    $("#performZDUDiv").attr("style", "display:none");

    var zduCompatibilityRequest = new XMLHttpRequest();
    zduCompatibilityRequest.open("GET", baseUrl + "/getZDUCompatibility/" + region + "/" + stack_name, true);
    zduCompatibilityRequest.setRequestHeader("Content-Type", "text/xml");
    zduCompatibilityRequest.addEventListener("load", processResponse);
    zduCompatibilityRequest.onreadystatechange = function () {
        if (zduCompatibilityRequest.readyState === XMLHttpRequest.DONE && zduCompatibilityRequest.status === 200) {
            var compatibility = JSON.parse(zduCompatibilityRequest.responseText);
            if (compatibility === true) {
                $("#zduCheckDiv").attr("style", "display:none");
                $("#performZDUDiv").removeAttr("style");
            } else {
                $("#zduCheckLbl").text("Stack is not ZDU compatible: " + compatibility);
            }
            $("#action-button").removeAttr("aria-disabled");

        }
    };
    zduCompatibilityRequest.send();
}

function beginUpgrade() {
    if (document.getElementById("zduCheckBox").checked) {
        $("#auth-ok-btn").on("click", performUpgrade);
        AJS.dialog2("#auth-dialog").show();
    }
    else {
        performUpgrade();
    }
}

function performUpgrade() {
    var zdu = document.getElementById("zduCheckBox").checked;
    var version = $("#upgradeVersionSelector").val();
    var stack_name = scrapePageForStackName();
    var url = baseUrl + "/do" + action + "/" + region + "/" + stack_name;

    var upgradeRequest = new XMLHttpRequest();
    url += "/" + version + "/" + zdu;

    upgradeRequest.open("POST", url, true);
    upgradeRequest.setRequestHeader('Content-Type', 'application/json; charset=UTF-8');
    upgradeRequest.addEventListener("load", processResponse);
    upgradeRequest.send(JSON.stringify(zdu ? getAuthDetailsAsJSON() : [{}]));

    redirectToLog(stack_name);
}