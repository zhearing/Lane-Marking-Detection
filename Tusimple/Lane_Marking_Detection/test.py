#!/usr/bin/env python
# coding=utf-8

import time
import os
from options.test_options   import TestOptions
from models.models          import create_model
#from util.visualizer        import Visualizer
#from util.recorder          import Recorder
from data.utils             import make_dataset
from data.transfer          import Transformer
from util.util              import save_image

opt         = TestOptions().parse()
model       = create_model(opt)
trans       = Transformer(opt)
save_dir    = opt.results_dir
if not os.path.exists(save_dir):
    os.makedirs(save_dir)

img_list    = make_dataset(opt.test_dir)
st          = time.time()
for i, img_path in enumerate(img_list):
    #def gao_image_path(self, image_path):
    img = trans.gao_image_path(img_path)
    img = (img).unsqueeze(0)
    model.set_input(img)
    cls, up, down = model.forward_input()

    img = model.draw(cls.data[0], up.data[0], down.data[0], opt.cls_thres)

    save_path = os.path.join(save_dir, img_path.replace('/', '_'))
    save_image(img, save_path)
    if i + 1 >= opt.ntest:
        break

num = len(img_list)
total_t = (time.time() - st) / 60.0
print(('Total time = %.2f min for %d samples' % (total_t, num)))
    






