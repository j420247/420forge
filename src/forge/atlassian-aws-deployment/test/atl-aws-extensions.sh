BASEDIR=$(dirname $0)
source $BASEDIR/atl-util.sh

STACK_NAME=

function atl_addProp {
  local TYPE=${1:?"A property type is required"}
  local VAL=${2:?"A property value is required"}
  echo "${AWS_REGION}=${VAL}" >> ~/.aws/$TYPE
}

function atl_createKeyPair {
  local KEY_NAME="$(whoami)-${AWS_REGION}"
  select yn in "Yes" "No"; do
    case $yn in
        Yes) 
          aws --region ${AWS_REGION} ec2 create-key-pair --key-name ${KEY_NAME} --query 'KeyMaterial' --output text > ${HOME}/.aws/${KEY_NAME}.pem
          echo "${KEY_NAME}"
          break;;
        No) 
          break;;
    esac
  done
}

function atl_createInternetGateway {
  local VPC_ID=${1:?"A VPC ID must be specified"}
  local IG_ID=$(aws --region ${AWS_REGION} ec2 create-internet-gateway --query 'InternetGateway.InternetGatewayId' | atl_unquote)
  aws --region ${AWS_REGION} ec2 attach-internet-gateway --vpc-id "${VPC_ID}" --internet-gateway-id "${IG_ID}"
  atl_addProp "ig" "${IG_ID}"  
  echo "${IG_ID}"
}

function atl_createRouteTable {
  local VPC_ID=${1:?"A VPC ID must be specified"}
  local IG_ID=${2:?"A Internet Gateway ID must be specified"}
  local ROUTE_TABLE=$(aws --region ${AWS_REGION} ec2 create-route-table --vpc-id ${VPC_ID} --query 'RouteTable.RouteTableId' | atl_unquote)
  atl_addProp "route-table" "${ROUTE_TABLE}"
  local ROUTE=$(aws --region ${AWS_REGION} ec2 create-route --route-table-id ${ROUTE_TABLE} --destination-cidr-block 0.0.0.0/0 --gateway-id ${IG_ID})
  echo ${ROUTE_TABLE}
}

function atl_createVPC {
  select yn in "Yes" "No"; do
    case $yn in
        Yes) 
          vpc=$(aws --region ${AWS_REGION} ec2 create-vpc --cidr-block 10.0.0.0/16 --query 'Vpc.VpcId' | atl_unquote);
          atl_tag "Name" "$(whoami)-${AWS_REGION}" "${vpc}"
          aws --region ${AWS_REGION} ec2 modify-vpc-attribute --vpc-id ${vpc} --enable-dns-hostnames >/dev/null
          ig_id=$(atl_createInternetGateway "${vpc}")
          echo "$vpc"
          break;;
        No) 
          break;;
    esac
  done
}

function atl_createSubnets {
  local IG_ID=$(_getProp "ig" "${AWS_REGION}")  
  select yn in "Yes" "No"; do
    case $yn in
        Yes)
          local AZS=( $(atl_queryAvailabilityZones) )
          subnet_1=$(aws --region ${AWS_REGION} ec2 create-subnet \
                        --vpc-id $1 \
                        --cidr-block 10.0.0.0/24 \
                        --availability-zone ${AZS[0]} \
                        --query 'Subnet.SubnetId' | atl_unquote);          
          subnet_2=$(aws --region ${AWS_REGION} ec2 create-subnet \
                        --vpc-id $1 \
                        --cidr-block 10.0.1.0/24 \
                        --availability-zone ${AZS[1]} \
                        --query 'Subnet.SubnetId' | atl_unquote);   
          atl_tag "Name" "$(whoami)-${AWS_REGION}" "${subnet_1}" "${subnet_2}"
          route_table=$(atl_createRouteTable $1 ${IG_ID})
          aws --region ${AWS_REGION} ec2 associate-route-table --subnet-id ${subnet_1} --route-table-id ${route_table} >/dev/null
          aws --region ${AWS_REGION} ec2 associate-route-table --subnet-id ${subnet_2} --route-table-id ${route_table} >/dev/null
          echo "$subnet_1\,$subnet_2"
          break;;
        No) 
          break;;
    esac
  done
}

function atl_deleteInternetGateway {
  local VPC_ID=${1:?"A VPC ID must be specified"}
  local IG_ID=$(_getProp "ig" "${AWS_REGION}")
  aws --region ${AWS_REGION} ec2 detach-internet-gateway --internet-gateway-id "${IG_ID}" --vpc-id "${VPC_ID}"
  aws --region ${AWS_REGION} ec2 delete-internet-gateway --internet-gateway-id "${IG_ID}"
  _removeProp "ig" "${AWS_REGION}"
  echo "Deleted Internet Gateway '${IG_ID}'"      
}

function atl_deleteSubnets {
  for subnet in $(atl_getSubnets | tr "\\\," "\n"); do
    aws --region "${AWS_REGION}" ec2 delete-subnet --subnet-id ${subnet}
    echo "Deleted Subnet '${subnet}'"
  done
  _removeProp "subnet" "${AWS_REGION}"
  local ROUTE_TABLE=$(_getProp "route-table" "${AWS_REGION}")
  if [[ -n ${ROUTE_TABLE} ]]; then
    aws --region ${AWS_REGION} ec2 delete-route-table --route-table-id ${ROUTE_TABLE}
    _removeProp "route-table" "${AWS_REGION}" 
    echo "Deleted Route Table '${ROUTE_TABLE}'"    
  fi
}

function atl_deleteKeyPair {
  local KEY_NAME=$(atl_getKeyName)
  local KEY_PATH="${HOME}/.aws/${KEY_NAME}.pem"
  if [[ -n ${KEY_NAME} ]]; then
    aws --region ${AWS_REGION} ec2 delete-key-pair --key-name ${KEY_NAME}
    chmod 700 ${KEY_PATH}
    rm ${KEY_PATH}
    _removeProp "key" "${AWS_REGION}"    
    echo "Deleted Key Pair '${KEY_NAME}'"  
  fi
}

function atl_deleteVPC {
  local VPC_ID=$(atl_getVpcId)
  atl_deleteInternetGateway "${VPC_ID}"
  aws --region "${AWS_REGION}" ec2 delete-vpc --vpc-id "${VPC_ID}"
  _removeProp "vpc" "${AWS_REGION}"
  echo "Deleted VPC '${VPC_ID}'"
}

function atl_ensureInternetGatewayAttached {
  local VPC_ID=${1:?"A VPC ID must be specified"}
  local IG_ID=$(aws --region "${AWS_REGION}" ec2 describe-internet-gateways \
  --filters "Name=attachment.vpc-id,Values=${VPC_ID}" --query 'InternetGateways[0].InternetGatewayId' | atl_unquote)
  if [[ -z $IG_ID ]]; then
    echo "The specified VPC does not have an Internet Gateway attached. Creating one..." 
    IG_ID=$(atl_createInternetGateway "${VPC_ID}")
    atl_addProp "ig" "${IG_ID}"
  fi
}

function atl_getBaseUrl {
  local STACK_NAME=${1:?"A stack name must be specified"}
  echo $(aws --region "${AWS_REGION}" cloudformation describe-stacks \
            --stack-name ${STACK_NAME} | jq -r '.Stacks[0].Outputs[] | select (.OutputKey=="URL") | .OutputValue')
}

function atl_getKeyName {
  _getProp "key" "${AWS_REGION}"
}

function atl_getVpcId {
  _getProp "vpc" "${AWS_REGION}"  
}

function atl_getSubnets {
  _getProp "subnet" "${AWS_REGION}"  
}

function atl_getStackName {
  STACK_NAME="$(whoami)-${1%.*}-$(date +%s)"
  echo "${STACK_NAME}"
}

function atl_propUsage {
  echo "Alternatively, add a '$1' file to your ~/.aws/ directory and map your key pair names for each region:"
  echo
  echo "        echo \"<region_name>=<$1_name>\" >> ~/.aws/$1"
  echo ''
}

function atl_queryAvailabilityZones {
  local AZS=$(aws --region ${AWS_REGION} ec2 describe-availability-zones --query 'AvailabilityZones[*].ZoneName' | jq '.[0:2] | join(",")' | atl_unquote)
  AZS=${AZS/,/ }
  echo "${AZS}"
}

function atl_runCleanup {
  echo "Would you like to clean up created resources?"
  select yn in "Yes" "No"; do
    case $yn in
        Yes) 
          aws --region "${AWS_REGION}" cloudformation delete-stack --stack-name "${STACK_NAME}"
          _waitForDelete "${STACK_NAME}"
          atl_deleteSubnets
          atl_deleteVPC
          atl_deleteKeyPair
          break;;
        No) 
          break;;
    esac
  done
}

function atl_tag {
  aws --region "${AWS_REGION}" ec2 create-tags \
      --tags "Key=$1,Value=$2" \
      --resources "${@:3}"
}

function atl_param {
  local KEY=${1:?"A key must be specified"}
  local VAL=${2:?"A value must be specified"}
  echo "ParameterKey=${KEY},ParameterValue=${VAL},UsePreviousValue=false"
}

function atl_waitForStack {
  local STACK_NAME=${1:?"A stack name must be specified"}
  until [ x`aws --region ${AWS_REGION} cloudformation describe-stacks --stack-name ${STACK_NAME} --query 'Stacks[0].StackStatus'` = 'x"CREATE_COMPLETE"' ]; do
    if [[ x`aws --region ${AWS_REGION} cloudformation describe-stacks --stack-name ${STACK_NAME} --query 'Stacks[0].StackStatus'` = 'x"ROLLBACK_COMPLETE"' ]]
    then 
      echo "Failed to create stack. Rolled back."
      exit 1
    fi
    echo -n .
    sleep 5
  done
  echo ''
  echo "Stack '${STACK_NAME}' successfully created."
}

function _stackStatus {
  aws --region ${AWS_REGION} cloudformation describe-stacks --stack-name ${STACK_NAME} --query 'Stacks[0].StackStatus' 2>&1
}

function _waitForDelete {
  local STACK_NAME=${1:?"A stack name must be specified"}
  echo "Waiting for stack '${STACK_NAME}' to be deleted..."
  until [[ $(_stackStatus) =~ "does not exist"  ]]; do
    if [[ x$(_stackStatus) = 'x"DELETE_FAILED"' ]]
    then 
      echo "Failed to delete stack."
      exit 1
    fi
    echo -n .
    sleep 5
  done
  echo ''
  echo "Stack '${STACK_NAME}' successfully deleted."
}

function _getProp {
  echo $(grep "^$2=" "${HOME}/.aws/$1" 2> /dev/null | cut -d'=' -f2)
}

function _removeProp {
  sed -i ".bak" "/^${2}=.*$/d" "${HOME}/.aws/$1"
  rm "${HOME}/.aws/$1.bak"
}