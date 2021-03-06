#!/usr/bin/env python
# coding=utf-8
'''
'raw_file':
'h_samples':
'lanes':
'originH':
'originW':
'color':
'type':
    self.parser.add_argument('--loadH',       type = int, default = 280, help = 'scale to H' )
    self.parser.add_argument('--loadW',       type = int, default = 350, help = 'scale to W' )
    self.parser.add_argument('--fineH',       type = int, default = 256, help = 'crop to H' )
    self.parser.add_argument('--fineW',       type = int, default = 320, help = 'crop to W' )
    self.parser.add_argument('--feaH',        type = int, default = 32,  help = 'feature for H')
    self.parser.add_argument('--feaW',        type = int, default = 40,  help = 'feature for W')
    self.parser.add_argument('--pos_thres',   type = int, default = 3,   help = 'positive threshold')
    self.parser.add_argument('--neg_thres',   type = int, default = 4,   help = 'negative threshold')
    self.parser.add_argument('--negpos_ratio',type = int, default = 10,  help = 'neg: pos ratio')
    self.parser.add_argument('--slicing',     type = int, default = 64,  help = '# of slicing parallel lines')
'''
import numpy as np
from PIL import Image
import random
from collections import OrderedDict
import torchvision.transforms as transforms
import torch

class Transformer():
    def __init__(self, opt):
        self.opt = opt
        self.opt.dh = self.opt.loadH - self.opt.fineH
        self.opt.dw = self.opt.loadW - self.opt.fineW
        assert self.opt.dh >= 0 and self.opt.dw >= 0, 'Warning: crop must be smaller or equal to load size!'
        self.randv  = []
        for i in range(self.opt.feaH):
            for j in range(self.opt.feaW):
                self.randv.append((i, j))

        transforms_list = []
        transforms_list += [transforms.ToTensor(),
                            transforms.Normalize((0.5, 0.5, 0.5), (0.5, 0.5, 0.5))]
        self.totensor = transforms.Compose(transforms_list)

    def label_feature(self, lane_array):
        eps = 1e-5
        # try to find positive samples
        record     = np.ones((self.opt.feaH, self.opt.feaW)) * (-1.0)
        record_min = np.ones((self.opt.feaH, self.opt.feaW)) * float('inf')
        slice_step_y = int(self.opt.fineH / self.opt.slicing)
        print(slice_step_y)
        y_slices = list(range(0, self.opt.fineH, slice_step_y))
        print(y_slices)
        assert len(y_slices) == self.opt.slicing, 'Warning: slicing number wrong!'

        fea_step_y = self.opt.fineH / self.opt.feaH
        fea_step_x = self.opt.fineW / self.opt.feaW

        lane_dict = [] # project y->x, y in slices
        for lane_id, lane in enumerate(lane_array):
            lanexs, laneys = lane[0], lane[1]
            if len(laneys) == 0:
                print((lane[0], lane[1]))
            yid = 0
            ylength = len(laneys)
            ldict = OrderedDict()
            for slice in y_slices:
                while yid + 1 < ylength and laneys[yid + 1] < slice:
                    yid += 1
                if laneys[yid] < slice + eps and yid + 1 < ylength and laneys[yid + 1] > slice - eps:
                    # slice -> x
                    x = lanexs[yid + 1] + 1.0 * (lanexs[yid] - lanexs[yid + 1]) / (laneys[yid + 1] - laneys[yid]) * (laneys[yid + 1] - slice)
                    ldict[slice] = x
                    
                    # (x, slice) to check positive samples
                    fea_x = int(x     / fea_step_x)
                    fea_y = int(slice / fea_step_y)
                    # not every slice has to be an grid !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
                    if slice % fea_step_y == 0 and 0 <= fea_x and fea_x < self.opt.feaW and 0 <= fea_y and fea_y < self.opt.feaH:
                        # in fea grid
                        assert fea_step_x % 2 == 0
                        dis = abs(x - fea_x * fea_step_x - fea_step_x / 2)
                        if dis < record_min[fea_y][fea_x]: # and dis < self.opt.pos_thres:
                            record_min[fea_y][fea_x] = dis
                            record[fea_y][fea_x]     = lane_id

            lane_dict.append(ldict)

        # filling class matrix
        # balance class
        pos_num = (record >= 0).sum()
        neg_mask= (record == -1.0)
        neg_num = neg_mask.sum()
        ignore_num = neg_num - pos_num * self.opt.negpos_ratio
        if ignore_num > 0:
            random.shuffle(self.randv)
            cnt = 0
            for i, v in enumerate(self.randv):
                y, x = v[0], v[1]
                if neg_mask[y][x]:
                    record[y][x] = -2.0
                    cnt += 1
                    if cnt == ignore_num:
                        break

        # now record is good, get it into classification label
        cls = np.copy(record)
        cls[record >= 0]  = 1  # positive
        cls[record == -1] = 0  # negative
        cls[record == -2] = -1 # ignore
        cls_mask = np.copy(cls)
        cls_mask[cls >= 0] = 1.0
        cls_mask[cls <  0] = 0.0

        res_cls      = torch.from_numpy(cls).unsqueeze(0).float() #.unsqueeze(0).float()
        res_cls_mask = torch.from_numpy(cls_mask).unsqueeze(0).float() #.unsqueeze(0).float()

        # filling up, down
        res_up        = torch.zeros((self.opt.slicing + 1, self.opt.feaH, self.opt.feaW))
        res_up_mask   = torch.zeros((self.opt.slicing + 1, self.opt.feaH, self.opt.feaW))
        res_down      = torch.zeros((self.opt.slicing + 1, self.opt.feaH, self.opt.feaW))
        res_down_mask = torch.zeros((self.opt.slicing + 1, self.opt.feaH, self.opt.feaW))

        #slice_step_y = self.opt.fineH / self.opt.slicing
        fea_step_y    = self.opt.fineH / self.opt.feaH
        fea_step_x    = self.opt.fineW / self.opt.feaW
        for h in range(self.opt.feaH):
            stdy = h * fea_step_y
            for w in range(self.opt.feaW):
                stdx = w * fea_step_x + 0.5 * fea_step_x
                lane_id = int(record[h][w])
                if lane_id < 0:
                    continue
                ld   = lane_dict[lane_id]

                # for up
                y_start = stdy
                y_id    = 0
                while True:
                    if not y_start in list(ld.keys()):
                        break
                    dx = ld[y_start] - stdx
                    res_up[y_id + 1][h][w]      = dx
                    res_up_mask[y_id + 1][h][w] = 1
                    y_id    += 1
                    y_start -= slice_step_y
                # number to regress
                res_up[0][h][w]      = y_id
                res_up_mask[0][h][w] = 1
                
                y_start = stdy + slice_step_y
                y_id    = 0
                while True:
                    if not y_start in list(ld.keys()):
                        break
                    dx = ld[y_start] - stdx
                    res_down[y_id + 1][h][w]      = dx
                    res_down_mask[y_id + 1][h][w] = 1
                    y_id    += 1
                    y_start += slice_step_y
                # number to regress
                res_down[0][h][w]      = y_id
                res_down_mask[0][h][w] = 1
        d = {'cls': res_cls, 'cls_mask': res_cls_mask, 'up': res_up, 'up_mask': res_up_mask, 'down': res_down, 'down_mask': res_down_mask}
        #return res_cls, res_cls_mask, res_up, res_up_mask, res_down, res_down_mask
        return d

    # last < 0 to be good value
    #    [-2, -2, 570, 554, 538, ..., 33, 16, -2,  -2, -2]
    # =>         [570, 554, 538, ..., 33, 16, -1, -18, -35]
    # =>         [y2,  y3,  y4,  ..., y...]
    def last_deal(self, xs, ys):
        le = xs.size
        pos_flag = False
        st = -1
        for i in range(le):
            if (not pos_flag) and xs[i] > 0:
                pos_flag = True
                st       = i
            if pos_flag and xs[i] < 0:
                #assert xs[i - 1] > 0 and xs[i - 2] > 0, 'Warning: before two elements are negative!'
                xs[i] = 2.0 * xs[i - 1] - xs[i - 2]
        #if st == -1 and self.opt.debug == 1:
        #    print xs
        #assert st != -1, 'st must be >= 0!'
        need_delete = False
        if st == -1:
            need_delete = True
            st = 0
        return np.array(xs[st: le]), np.array(ys[st: le]), need_delete

    # parse label into array, fitting, and calculate the last < 0
    def parse_label(self, label):
        #y_mul = 1.0 / label['originH'] * self.opt.loadH
        #x_mul = 1.0 / label['originW'] * self.opt.loadW
        y_mul = 1.0 / 720 * self.opt.loadH
        x_mul = 1.0 / 1280 * self.opt.loadW
        lane_array = []
        std_ys = np.array(label['h_samples']) * y_mul
        for lane in label['lanes']:
            #print('lane x len = ', len(lane))
            #if self.opt.debug == 1:
            #    print np.array(lane)
            xs = np.array(lane) * x_mul
            # recalculate and short array, make last < 0 to be good value
            if (len(xs) != len(std_ys)):
                print(xs, std_ys)
            assert(len(xs) == len(std_ys))
            xs, ys, need_delete = self.last_deal(xs, std_ys)
            if not need_delete:
                lane_array.append([xs, ys])
        return lane_array


    def gao_image_path(self, image_path):
        image = Image.open(image_path).convert('RGB')
        width, height = image.size
        if width != self.opt.loadW or height != self.opt.loadH:
            image = image.resize((self.opt.loadW, self.opt.loadH), Image.BILINEAR)
        image = self.totensor(image)
        return image


    def gao(self, image, label, phase):
        lane_array = self.parse_label(label)
        if phase == 'train':
            width, height = image.size
            if width != self.opt.loadW or height != self.opt.loadH:
                image = image.resize((self.opt.loadW, self.opt.loadH), Image.BILINEAR)
            # ------------------------------------------------------------------------
            # crop !
            # parallel gao image and label
            dx = random.randint(0, self.opt.dw)
            dy = random.randint(0, self.opt.dh)
            image = image.crop((dx, dy, dx + self.opt.fineW, dy + self.opt.fineH))
            for i in range(len(lane_array)):
                lane_array[i][0] = lane_array[i][0] - dx
                lane_array[i][1] = lane_array[i][1] - dy

            # ------------------------------------------------------------------------
            # horizontal flip !
            # parallel gao image and label
            flip_flag = random.randint(0, 100)
            if flip_flag > 50:
                image = image.transpose(Image.FLIP_LEFT_RIGHT)
                for i in range(len(lane_array)):
                    lane_array[i][0] = self.opt.fineW - 1 - lane_array[i][0]
        
        image = self.totensor(image)
        label = self.label_feature(lane_array)
        #print('image.shape = ', image.shape)
        return image, label


