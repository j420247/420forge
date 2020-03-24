// JS helpers
function countOccurences(stringToSearch, searchTerm) {
    var count = 0;
    var position = stringToSearch.indexOf(searchTerm);
    while (position > -1) {
        ++count;
        position = stringToSearch.indexOf(searchTerm, ++position);
    }
    return count;
}

function removeElementsByClass(className){
    var elements = document.getElementsByClassName(className);
    while(elements.length > 0){
        elements[0].parentNode.removeChild(elements[0]);
    }
}

function notify(message) {
    if ("Notification" in window) {
        if (Notification.permission === "granted") {
            var notification = new Notification('Forge', {body: message, icon: '/static/img/Atlassian-vertical-blue@2x-rgb.png'});
        }
        else if (Notification.permission !== "denied") {
            Notification.requestPermission().then(function (permission) {
                if (permission === "granted") {
                    var notification = new Notification('Forge', {body: message, icon: '/static/img/Atlassian-vertical-blue@2x-rgb.png'});
                }
            });
        }
    }
}

// Find and return the value from a JSON object inside an array of JSON objects (case insensitive)
var getObjectFromArrayByValue = function (array, key, value) {
    var obj = array.filter(function (object) {
        return object[key].toLowerCase() === value.toLowerCase();
    });
    return obj[0].Value;
};

// API helpers
function send_http_get_request(url, onreadystatechange, optionalFunctionParams) {
    var getRequest = new XMLHttpRequest();
    getRequest.open("GET", url, true);
    getRequest.setRequestHeader("Content-Type", "text/xml");
    getRequest.addEventListener("load", processResponse);
    if (onreadystatechange) {
        getRequest.onreadystatechange = function () {
            if (getRequest.readyState === XMLHttpRequest.DONE && getRequest.status === 200) {
                if (optionalFunctionParams)
                    onreadystatechange(getRequest.responseText, optionalFunctionParams);
                else
                    onreadystatechange(getRequest.responseText);
            }
        };
    }
    getRequest.send();
}

function send_http_post_request(url, data, onreadystatechange) {
    var postRequest = new XMLHttpRequest();
    postRequest.open("POST", url, true);
    postRequest.setRequestHeader("Content-Type", "application/json; charset=UTF-8");
    postRequest.addEventListener("load", processResponse);
    if (onreadystatechange) {
        postRequest.onreadystatechange = function () {
            if (postRequest.readyState === XMLHttpRequest.DONE && postRequest.status === 200)
                onreadystatechange(postRequest.responseText);
        };
    }
    postRequest.send(data);
    return postRequest;
}

// Create/modify page elements
function createSingleSelect(parameterKey, defaultValue, dropdownOptions, placeholder='') {
    // determine whether the dropdownOptions includes labels or not
    var hasLabels = typeof dropdownOptions[0] === 'object' ? true : false;

    // build an array of strings to represent HTML aui-select element
    var singleSelectHtml = [];
    singleSelectHtml.push(`<aui-select id=${parameterKey + "Val"} name=${parameterKey + "DropdownDiv"} placeholder="${placeholder}">`);
    for (var option of dropdownOptions) {
        var html_value = hasLabels ? option['value'] : option;
        var html_label = hasLabels ? option['label'] : option;
        var html_selected = defaultValue.toString() === html_label.toString() ? ' selected' : '';
        singleSelectHtml.push(`<aui-option value="${html_value}"${html_selected}>${html_label}</aui-option>`);
    }
    singleSelectHtml.push("</aui-select>");

    // build HTML from the array of strings
    var singleSelect = $(singleSelectHtml.join(''));

    // attach change event handler, if applicable
    if (parameterKey === 'VPC') {
        singleSelect.change(function (data) {
            getSubnets(this.value, 'update');
        });
    } else if (parameterKey === 'SSLCertificateARN') {
        singleSelect.change(function (data) {
            $('#TomcatSchemeVal')[0].value = this._input.value === '' ? 'http' : 'https';
        });
    }

    // return the element for DOM insertion
    return singleSelect;
}

function createMultiSelect(parameterKey, defaultValue, multiSelectOptions, div) {
    var multiSelect = document.createElement("SELECT");
    multiSelect.className = "multi-select";
    multiSelect.id = parameterKey + "Val";
    multiSelect.name = parameterKey + "Val";
    multiSelect.multiple = "multiple";
    multiSelect.size = "4";

    for (var opt in multiSelectOptions) {
        var option = document.createElement("OPTION");
        option.innerText = multiSelectOptions[opt];
        multiSelect.appendChild(option);
    }

    $("#" + parameterKey + "Val").remove();
    $(multiSelect).insertBefore($(div).children().last(), null);
}

function createInputParameter(param, fieldset) {
    var div = document.createElement("DIV");
    div.className = "field-group param-field-group";
    div.id = param.ParameterKey + "Div";
    div.name = "parameter";

    var label = document.createElement("LABEL");
    label.className = "paramLbl";
    label.htmlFor = param.ParameterKey + "Val";
    label.innerHTML = param.ParameterKey;
    div.appendChild(label);

    if (param.AllowedValues) {
        var input = createSingleSelect(param.ParameterKey, param.ParameterValue, param['AllowedValues']);
    } else if (param.ParameterKey === "VPC") {
        if (action === 'clone')
            getVPCs($("#regionSelector")[0].value);
        else
            getVPCs(region, param.ParameterValue);
    } else if (param.ParameterKey === "KmsKeyArn") {
        if (action === 'clone')
            getKmsKeys($("#regionSelector")[0].value);
        else
            getKmsKeys(region, param.ParameterValue);
    } else if (param.ParameterKey === "SSLCertificateARN") {
        if (action === 'clone')
            getSslCerts($("#regionSelector")[0].value);
        else
            getSslCerts(region, param.ParameterValue);
    } else {
        var input = document.createElement("INPUT");
        input.className = "text";
        input.id = param.ParameterKey + "Val";
        input.value = param.ParameterValue;

        if (param.ParameterKey === "DBMasterUserPassword" || param.ParameterKey === "DBPassword") {
            if (action === 'clone' || action === 'create') {
                input.setAttribute("data-aui-validation-field", "");
                input.setAttribute("data-aui-validation-pattern-msg", "Value must satisfy regular expression pattern: " + param.AllowedPattern);
                input.type = "password";
                input.value = "";
                input.required = true;
                input.pattern = param.AllowedPattern;
            } else if (action === 'update'){
                // don't display passwords in the update action
                return;
            }
        } else if ((param.ParameterKey === "KeyName" || param.ParameterKey === "KeyPairName") && $("meta[name=ssh_key_name]").attr("value") !== "") {
            input.value = $("meta[name=ssh_key_name]").attr("value");
        } else if (param.ParameterKey === "HostedZone" && $("meta[name=hosted_zone]").attr("value") !== "") {
            input.value = $("meta[name=hosted_zone]").attr("value");
        }
        if (param.AllowedPattern) {
            input.setAttribute("data-aui-validation-field", "");
            input.setAttribute("data-aui-validation-pattern-msg","Value must satisfy regular expression pattern: " + param.AllowedPattern);
            input.pattern = param.AllowedPattern;
        }
        if (param.MinValue) {
            input.setAttribute("data-aui-validation-field", "");
            input.type = "number";
            input.min = param.MinValue;
        }
        if (param.MaxValue) {
            input.setAttribute("data-aui-validation-field", "");
            input.type = "number";
            input.max = param.MaxValue;
        }
        if (param.MinLength) {
            input.setAttribute("data-aui-validation-field", "");
            input.minLength = param.MinLength;
        }
        if (param.MaxLength) {
            input.setAttribute("data-aui-validation-field", "");
            input.maxLength = param.MaxLength;
        }
    }
    if (typeof input !== 'undefined') {
        $(div).append(input);
    }
    if (param.ParameterDescription) {
        var description = document.createElement("DIV");
        description.className = "description";
        description.innerText = param.ParameterDescription;
        div.appendChild(description);
    }
    fieldset.appendChild(div);
}

function updateMultiSelect(parameterKey, defaultValue, multiSelectOptions) {
    var multiSelect = document.getElementById(parameterKey + "Val");

    while (multiSelect.firstChild)
        multiSelect.removeChild(multiSelect.firstChild);

    for (var opt in multiSelectOptions) {
        var option = document.createElement("OPTION");
        option.innerText = multiSelectOptions[opt];
        multiSelect.appendChild(option);
    }
}

function addStackDropdown() {
    var stacks = document.getElementsByClassName("selectStackOption");
    for (var i = 0; i < stacks.length; i++) {
        stacks[i].addEventListener("click", function (data) {
            selectStack(data.target.text);
            enableActionButton();
        }, false);
    }
}

function addDefaultActionButtonListener() {
    var actionButton = document.getElementById("action-button");
    if (actionButton)
        actionButton.addEventListener("click", performAction);
}

function enableActionButton() {
    $("#action-button").attr("aria-disabled", false);
}

function disableActionButton() {
    $("#action-button").attr("aria-disabled", true);
}

function replaceModalContents(title, text, optional_elements) {
    var modalTitleElement = $("#modal-title");
    modalTitleElement.empty();
    modalTitleElement.text(title);

    var modalContentsElement = $("#modal-contents");
    modalContentsElement.empty();
    modalContentsElement.append("<p>" + text + "</p>");

    if (optional_elements)
        modalContentsElement.append(optional_elements);
}

// Forge common functions
function checkAuthenticated() {
    var stacks = document.getElementsByClassName("selectStackOption");
    if (stacks.length === 1 && stacks[0].text === 'No credentials') {
        displayAUIFlag('No credentials - please authenticate with Cloudtoken', 'error', 'manual');
    }
}

function scrapePageForStackName() {
    var stack_name = $("#stackName").text();
    if (!stack_name) {
        stack_name = $("#StackNameVal").val();
    }
    return stack_name;
}

function getAuthDetailsAsJSON() {
    var username = $('#username').val();
    var password = $('#password').val();
    var jsonArray = [];
    var authDetails = {};
    authDetails["username"] = username;
    authDetails["password"] = password;
    jsonArray.push(authDetails);
    return jsonArray;
}

function redirectToLog(stack_name, extra_params) {
    // Wait a mo for action to begin  in backend
    setTimeout(function () {
        // Redirect to action progress screen
        var url = baseUrl + "/actionprogress/" + action + "?stack=" + stack_name;
        if (extra_params)
            url += extra_params;
        window.location = url;
    }, 1000);
}

function processResponse() {
    if (this.status !== 200) {
        window.location = baseUrl + "/error/" + this.status;
    }
}

function displayAUIFlag(message, category, closes = 'auto') {
    // useful when we don't want a page reload which is required for flask's 'flash'
    AJS.flag({
         type: category,
         body: message,
         close: closes
    });
}

function setModalSize(selector, size) {
    $(selector)
        .removeClass(function (index, className) {
            return (className.match (/(^|\s)aui-dialog2-(small|medium|large|xlarge)/g) || []).join(' ');
        })
        .addClass('aui-dialog2-' + size);
}

// https://developer.mozilla.org/en-US/docs/Web/API/WindowBase64/Base64_encoding_and_decoding
function Base64Encode(str, encoding = 'utf-8') {
    var bytes = new (typeof TextEncoder === "undefined" ? TextEncoderLite : TextEncoder)(encoding).encode(str);
    return base64js.fromByteArray(bytes);
}

function Base64Decode(str, encoding = 'utf-8') {
    var bytes = base64js.toByteArray(str);
    return new (typeof TextDecoder === "undefined" ? TextDecoderLite : TextDecoder)(encoding).decode(bytes);
}

// Common functions for node selection and CPU display
function emptyNodeListAndCpuChart() {
    $("#nodesList").empty();
    $("#nodeSelector")[0].text = "Select Node";
    $("#cpuChartDiv").empty();
    $("#cpuChartDiv").append("<canvas id='cpuChart' hidden>");
}

function listNodes(stack_name) {
    // Add a spinner
    if ($("#nodesList").find(".aui-spinner").length === 0) {
        $("#nodesList").empty();
        var li = document.createElement("li");
        var spinner = document.createElement("aui-spinner");
        spinner.setAttribute("size", "small");
        li.appendChild(spinner);
        $("#nodesList").append(li);
    }
    // If nodes not yet in stack info, sleep 1s
    if ($('#nodes .nodes').length === 0 && $('#nodes').text() !== 'None') {
        setTimeout(function() {
            listNodes(stack_name)
        }, 1000);
        return;
    }
    // Get nodes
    var nodes = [];
    $.each($('.nodes'), function() {
        nodes.push(this.innerText.substr(0, this.innerText.indexOf(':')));
    });
    // Remove existing nodes/spinner
    $("#nodesList").empty();
    // Add each node to dropdown
    for (var node in nodes) {
        var li = document.createElement("LI");
        var anchor = document.createElement("A");
        anchor.className = "selectNodeOption";
        var text = document.createTextNode(nodes[node]);
        anchor.appendChild(text);
        li.appendChild(anchor);
        $("#nodesList").append(li);
    }
    // Add onClick event listener to each node
    $(".selectNodeOption").click(function() {
        var selectedNode = this.innerText;
        $("#nodeSelector").text(selectedNode);
        $("#takeThreadDumps").removeAttr("disabled");
        $("#takeHeapDumps").removeAttr("disabled");
        $("#drainNodes").removeAttr("disabled");
        $("#cpuChartDiv").empty();
        $("#cpuChartDiv").append("<canvas id='cpuChart' class='cpuChartEmpty' hidden>");
        drawChart([],[], '');
        getNodeCPU(this.innerText);
        enableActionButton();
    });
}

function getNodeCPU(node) {
    var stack_name = scrapePageForStackName();
    var url = [baseUrl, 'getNodeCPU', region, stack_name, node].join('/');
    send_http_get_request(url, displayNodeCPU);
}

function drawChart(timestamps_sorted, cpu_sorted, border_color) {
    var ctx = document.getElementById('cpuChart').getContext('2d');
    new Chart(ctx, {
        type: 'line',
        data: {
            labels: timestamps_sorted,
            datasets: [{
                label: 'CPU Utilization over the last 30 minutes',
                backgroundColor: 'rgba(255, 255, 255, 0)',
                borderColor: border_color,
                data: cpu_sorted
            }]
        },
        options: {
            scales: {
                yAxes: [{
                    ticks: {
                        suggestedMin: 0,
                        suggestedMax: 100
                    }
                }]
            }
        }
    });
}

function displayNodeCPU(responseText) {
    var cpu_data_dict = JSON.parse(responseText);
    var timestamps = Object.keys(cpu_data_dict);
    timestamps.sort();
    var timestamps_sorted = [];
    var cpu_sorted = [];
    for (var i = 0; i < timestamps.length; i++) {
        var date = new Date(parseInt(timestamps[i]) * 1000);
        var month = date.getMonth() + 1;
        var day_num = date.getDate().toString().length === 1 ? "0" + date.getDate() : date.getDate();
        var hours = date.getHours().toString().length === 1 ? "0" + date.getHours() : date.getHours();
        var minutes = date.getMinutes().toString().length === 1 ? "0" + date.getMinutes() : date.getMinutes();
        timestamps_sorted.push(month + "/" + (day_num) + " " + hours + ":" + minutes);
        cpu_sorted.push(cpu_data_dict[timestamps[i]]);
    }

    var border_color = '#00875A';
    for (var i = cpu_sorted.length - 6; i < cpu_sorted.length; i++) {
        if (cpu_sorted[i] > 80) {
            border_color = '#DE3505';
            break;
        }
    }
    drawChart(timestamps_sorted, cpu_sorted, border_color);
    $("#cpuChart").removeClass("cpuChartEmpty");
    $("#cpuChart").removeAttr("hidden");
}
