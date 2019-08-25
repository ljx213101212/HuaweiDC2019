通过如下链接或竞赛平台赛题说明页面下载数据集 garbage_classify.zip:
https://modelarts-competitions.obs.cn-north-
1.myhuaweicloud.com/garbage_classify/dataset/garbage_classify.zip。
将数据集 garbage_classify.zip 下载至本地后解压缩datasets下

cd src
python3 run.py --data_url='../datasets/garbage_classify/train_data' --train_url='../model_snapshots' --num_classes=40 --deploy_script_path='./deploy_scripts' --test_data_url='../datasets/test_data' --max_epochs=50

