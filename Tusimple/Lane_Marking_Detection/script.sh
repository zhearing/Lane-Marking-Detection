python train.py --dataroot /media/zyzhong/Data/data3/XJTU2017/task_1/Tusimple/ --name lane_resnext101 --gpu_ids 0 --batchSize 1

python test.py --name lane_resnext101 --gpu_ids 0 --test_dir /media/zyzhong/Data/data3/XJTU2017/task_1/Tusimple/test_set/ --results_dir ./tusimple_tests/ --cls_thres 0.9

python test.py --name lane_resnext101 --gpu_ids 0 --test_dir /media/zyzhong/Data/data3/XJTU2017/task_1/1495485141585513338/ --results_dir ./tusimple_tests/ --which_epoch 136 --cls_thres 0.9
