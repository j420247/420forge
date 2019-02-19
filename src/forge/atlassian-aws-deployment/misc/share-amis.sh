BASEDIR=$(dirname $0)
echo "Sharing CloudFormation template AMI mapping(s)... with acc ${1}"
TEMPLATES=$(find ${BASEDIR}/../templates -iname "*.template" -maxdepth 1)

for template in ${TEMPLATES[@]}; do
    jq -r  ".Mappings.AWSRegionArch2AMI|keys[]" ${template} | while read key; do 
        AMI_ID=$(jq -r ".Mappings.AWSRegionArch2AMI[\"$key\"].HVM64" ${template})
        echo "Sharing AMI ${AMI_ID}"
        aws --region ${key} ec2 modify-image-attribute --image-id ${AMI_ID} --launch-permission "{\"Add\":[{\"UserId\":\"${1}\"}]}"
    done
done