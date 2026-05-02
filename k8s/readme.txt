此目录专为适配 K8s 环境运行

前置需要做的事：

  SSH key相关：
  1. 如果需要管理的主机内没有相同用户，建议使用ansible等工具创建vmcontrolhub用户，请确保vmcontrolhub用户拥有家目录，拥有sudo qm/virsh等命令的权限
  2. 为vmcontrolhub用户创建SSH key,在 K8s 环境下，没必要给ssh key 文件单独挂载，更推荐Secert资源对象，其中的type: kubernetes.io/ssh-auth更是极其适配
  3. 在项目目录运行此命令 ssh-keygen -t rsa -b 2048 -f ./id_rsa -N "" -q 可以创建公钥和私钥，当然如果直接复用服务器内相同用户的话，这一步是不需要做的
  4. 将生成的或已有的公钥私钥文件复制进 k8s/secrets.yaml中的ssh-keys-secret

  持久化存储相关：
  1. 在k8s/mysql.yaml中的storageClassName: your_storageclass_name替换为集群内已有的StorageClass

  外部入口相关：
  此项目只提供了对接Gateway API的 httproute 文件
  1. 将k8s/app-svc-httproute.yaml中的spec.parentRefs.name：your_gateway_name 替换为集群内已有的Gateway
  2. 将k8s/app-svc-httproute.yaml中的spec.hostnames.：your_hostname.com 替换为您为该项目定义的域名
  3. 将k8s/app-svc-httproute.yaml中的spec.namespace: your_gateway_namespeac 替换为Gayeway所在的namespace
  4. 将k8s/app-svc-httproute.yaml中的spec.sectionName: your_gateway_listener_name 替换为Gateway中存在的listener name

运行项目/创建资源对象:
# 第一次创建由于命名空间的问题，会提示命名空间不存在，执行两次即可
kubectl apply -f k8s/

# 查看各资源对象的运行状态
kubectl get all -n vmcontrolhub

为您的vmcontrolhub创建一个超级用户，将 your_pod_name 替换为 kubectl get all -n vmcontrolhub 获取到的 Pod name
kubectl exec -it -n vmcontrolhub  your_pod_name -c app -- python /home/vmcontrolhub/manage.py createsuperuser
