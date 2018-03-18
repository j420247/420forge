$(document).unbind('ready');

$(document).ready(function() {
    var stacks = document.getElementsByClassName("selectStackOption");
    var stackName = "none";

    for (var i = 0; i < stacks.length; i++) {
        stacks[i].addEventListener("click", function (data) {
            stackName = data.target.text;
            selectStack(stackName);
        }, false);
    }
});

function selectStack(stackName) {
    $("#stackSelector").text(stackName);
    $("#stackName").text(stackName);

    var baseUrl = window.location .protocol + "//" + window.location.host;
    var env = 'prod';

    var ebsSnapshotRequest = new XMLHttpRequest();
    ebsSnapshotRequest.open("GET", baseUrl  + "/getEbsSnapshots/" + stackName, true);
    ebsSnapshotRequest.setRequestHeader("Content-Type", "text/xml");
    ebsSnapshotRequest.onreadystatechange = function () {
        if (ebsSnapshotRequest.readyState === XMLHttpRequest.DONE && ebsSnapshotRequest.status === 200) {
            var ebsSnapDropdown = document.getElementById("ebsSnapshots");
            while (ebsSnapDropdown.firstChild) {
                ebsSnapDropdown.removeChild(ebsSnapDropdown.firstChild);
            }

            var ebsSnaps = JSON.parse(ebsSnapshotRequest.responseText);
            ebsSnaps.sort(function(a, b) {
                return - a.localeCompare(b)});

            for (var snap in ebsSnaps) {
                console.log(ebsSnaps[snap]);
                var li = document.createElement("LI");
                var text = document.createTextNode(ebsSnaps[snap]);
                text.className = "selectEbsSnapshotOption";
                li.appendChild(text);
                ebsSnapDropdown.appendChild(li);
            }

            var ebsSnaps = document.getElementsByClassName("selectEbsSnapshotOption");
            for (var i = 0; i < ebsSnaps.length; i++) {
                ebsSnaps[i].addEventListener("click", function (data) {
                    var ebsSnap = data.target.text;
                    selectEbsSnap(ebsSnap);
                }, false);
            }
        }
    };
    ebsSnapshotRequest.send();

    var rdsSnapshotRequest = new XMLHttpRequest();
    rdsSnapshotRequest.open("GET", baseUrl  + "/getRdsSnapshots/" + stackName, true);
    rdsSnapshotRequest.setRequestHeader("Content-Type", "text/xml");
    rdsSnapshotRequest.onreadystatechange = function () {
        if (rdsSnapshotRequest.readyState === XMLHttpRequest.DONE && rdsSnapshotRequest.status === 200) {
            var rdsSnapDropdown = document.getElementById("rdsSnapshots");
            while (rdsSnapDropdown.firstChild) {
                rdsSnapDropdown.removeChild(rdsSnapDropdown.firstChild);
            }

            var rdsSnaps = JSON.parse(rdsSnapshotRequest.responseText);
            rdsSnaps.sort(function(a, b) {
                return - a.localeCompare(b)});

            for (var snap in rdsSnaps) {
                console.log(rdsSnaps[snap]);
                var li = document.createElement("LI");
                var text = document.createTextNode(rdsSnaps[snap]);
                text.className = "selectRdsSnapshotOption";
                li.appendChild(text);
                rdsSnapDropdown.appendChild(li);
            }

            var rdsSnaps = document.getElementsByClassName("selectRdsSnapshotOption");
            for (var i = 0; i < rdsSnaps.length; i++) {
                rdsSnaps[i].addEventListener("click", function (data) {
                    var rdsSnaps = data.target.text;
                    selectRdsSnap(rdsSnaps);
                }, false);
            }
        }
    };
    rdsSnapshotRequest.send();

    var stackParamsRequest = new XMLHttpRequest();
    stackParamsRequest.open("GET", baseUrl  + "/stackParams/" + env + "/" + stackName, true);
    stackParamsRequest.setRequestHeader("Content-Type", "text/xml");
    stackParamsRequest.onreadystatechange = function () {
        if (stackParamsRequest.readyState === XMLHttpRequest.DONE && stackParamsRequest.status === 200) {
            var product;
            params = JSON.parse(stackParamsRequest.responseText);
            params.sort(function(a, b) {
                return a.ParameterKey.localeCompare(b.ParameterKey)});

            $("#paramsForm").html("");
            $("#paramsForm").className = "aui long-label";

            var fieldset = document.createElement("FIELDSET");
            fieldset.id = "fieldSet";

            var stackNameParam = {
                "ParameterKey": "StackName",
                "ParameterValue": ""
            };
            createInputParameter(stackNameParam, fieldset);

            for (var param in params) {
                createInputParameter(params[param], fieldset);
                if (params[param].ParameterKey == "ConfluenceVersion") {
                    product = "Confluence";
                }
            }

            var paramsForm = document.getElementById("paramsForm");
            paramsForm.appendChild(fieldset);

            document.getElementById("CatalinaOptsVal").value += "-Datlassian.mail.senddisabled=true " +
                "-Datlassian.mail.fetchdisabled=true " +
                "-Datlassian.mail.popdisabled=true";
            if (product == "Confluence") {
                document.getElementById("CatalinaOptsVal").value += " -Dconfluence.disable.mailpolling=true";
            }
        }
    };
    stackParamsRequest.send();

    function createInputParameter(param, fieldset) {
        var div = document.createElement("DIV");
        div.className = "field-group";
        div.id = "fieldGroup";

        var label = document.createElement("LABEL");
        label.htmlFor = param.ParameterKey + "Val";
        label.innerHTML = param.ParameterKey;
        div.appendChild(label);

        var input = document.createElement("INPUT");
        input.className = "text";
        input.id = param.ParameterKey + "Val";
        input.value = param.ParameterValue;
        div.appendChild(input);

        fieldset.appendChild(div);
    }
}

function selectEbsSnap(ebsSnap) {
    $("#ebsSnapshotSelector").text(ebsSnap);
}

function selectRdsSnap(rdsSnap) {
    $("#rdsSnapshotSelector").text(rdsSnap);
}