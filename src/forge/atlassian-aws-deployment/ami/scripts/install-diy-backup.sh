#!/bin/bash
set -e
set -x

DIY_BACKUP_DISPLAY_NAME=${DIY_BACKUP_DISPLAY_NAME:?"The diy backup name must be supplied"}
DIY_BACKUP_CLONE_URL=${DIY_BACKUP_CLONE_URL:?"The ${DIY_BACKUP_DISPLAY_NAME} clone URL must be supplied"}
DIY_BACKUP_PUBLIC_REMOTE=${DIY_BACKUP_PUBLIC_REMOTE:?"The DIY_BACKUP_PUBLIC_REMOTE URL must be supplied"}
DIY_BACKUP_CLONE_PATH=${DIY_BACKUP_CLONE_PATH:?"The ${DIY_BACKUP_DISPLAY_NAME} clone directory must be supplied"}
DIY_BACKUP_CLONE_BRANCH=${DIY_BACKUP_CLONE_BRANCH:?"The ${DIY_BACKUP_DISPLAY_NAME} clone branch must be supplied"}
DIY_BACKUP_USER=${DIY_BACKUP_USER:?"THE ${DIY_BACKUP_USER} name must be supplied"}

echo "Cloning ${DIY_BACKUP_DISPLAY_NAME} branch ${DIY_BACKUP_CLONE_BRANCH} from ${DIY_BACKUP_CLONE_URL} into ${DIY_BACKUP_CLONE_PATH}"
if [ ! -d "${DIY_BACKUP_CLONE_PATH}" ]; then
    sudo mkdir -p ${DIY_BACKUP_CLONE_PATH}
    sudo chown "${DIY_BACKUP_USER}":"${DIY_BACKUP_USER}" "${DIY_BACKUP_CLONE_PATH}"
fi
sudo su ${DIY_BACKUP_USER} -c "git clone --branch ${DIY_BACKUP_CLONE_BRANCH} -- ${DIY_BACKUP_CLONE_URL} ${DIY_BACKUP_CLONE_PATH}"
sudo su ${DIY_BACKUP_USER} -c "cp ${DIY_BACKUP_CLONE_PATH}/bitbucket.diy-backup.vars.sh.example-aws ${DIY_BACKUP_CLONE_PATH}/bitbucket.diy-backup.vars.sh"
pushd ${DIY_BACKUP_CLONE_PATH}
echo "Setting origin remote url to ${DIY_BACKUP_PUBLIC_REMOTE}"
git remote set-url origin "${DIY_BACKUP_PUBLIC_REMOTE}"
popd

echo "${DIY_BACKUP_DISPLAY_NAME} installation completed"