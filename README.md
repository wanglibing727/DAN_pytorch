# DAN_pytorch
## 1. 介绍

​        本项目为算法《Decoupled Attention Network for Text Recognition》的 pytorch 版本复现，原作者项目地址（https://github.com/Wang-Tianwei/Decoupled-attention-network）。需说明的是，本人只是对作者的项目进行了小修改，大部分和作者的一致，只是本人在跑作者的代码时很难工作。本项目，本人亲测可用，并且本人已进行自己的数据集的实验。

## 2. 环境依赖

opencv_python==4.5.3.56
torchvision==0.9.0
numpy==1.21.1
lmdb==1.2.1
editdistance==0.5.3
torch==1.8.0
six==1.16.0
Pillow==8.3.2

## 3. 制作lmdb数据集

​          首先在文件夹准备好自己所用的图片数据，我一般习惯将图片命名为 number_label.png的形式，并且制作txt文件保存训练集和测试集（train.txt, test.txt），分别保存数据的文件名（示例：1_hello.png），然后运行本项目中 create_lmdb.py ，自己根据自己准备的图片数据以及txt文件修改相关的路径。

## 4. 运行

​         根据自己的要求修改 cfg.py ，然后运行 main.py 文件即可。

## 5. 可能发生的情况

​         将测试集的 batch_size 设置过高容易爆显存 （32 GB都干满了），gpu占用好像会一点点变高，然后稳定下来。

## Citation

```
@InProceedings{DAN_aaai20,
  author = {Tianwei Wang and Yuanzhi Zhu and Lianwen Jin and Canjie Luo and Xiaoxue Chen and Yaqiang Wu and Qianying Wang and Mingxiang Cai}, 
  title = {Decoupled attention network for text recognition}, 
  booktitle ={AAAI Conference on Artificial Intelligence}, 
  year = {2020}
}
```

