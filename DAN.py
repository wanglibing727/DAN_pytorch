# encoding: utf-8"""@Time: 2021-07-19 20:17 @Author: Libing Wang@File: DAN.py @description: """import torchimport torch.nn as nnimport torch.nn.functional as Ffrom torch.nn.parameter import Parameterfrom resnet import resnet_45class FeatureExtractor(nn.Module):    def __init__(self, strides, input_shape):        super(FeatureExtractor, self).__init__()        self.model = resnet_45(strides)        self.input_shape = input_shape    def forward(self, x):        features = self.model(x)        return features    def need_shapes(self):        """        torch.Size([1, 32, 16, 64])        torch.Size([1, 128, 8, 32])        torch.Size([1, 512, 8, 32])        """        pseudo_input = torch.rand(1, self.input_shape[0], self.input_shape[1], self.input_shape[2])        outs = self.model(pseudo_input)        return [out.size()[1:] for out in outs]class CAM(nn.Module):    def __init__(self, scales, maxT, depth, num_channels):        """scales 即为 上述 need_shapes() 的输出， 也就是 每个特征图的shape [c, h, w]"""        super(CAM, self).__init__()        fpn = []        for i in range(1, len(scales)):            assert not (scales[i - 1][1] / scales[i][1]) % 1, "layers scale error, from {} to {}".format(i - 1, 1)            assert not (scales[i - 1][2] / scales[i][2]) % 1, "layers scale error, from {} to {}".format(i - 1, 1)            kernel_size = [3, 3, 5]  # if down_sample ratio >= 3 , the kernel size is 5, else 3            ratio_h, ratio_w = scales[i - 1][1] // scales[i][1], scales[i - 1][2] // scales[i][2]            kernel_size_h = 1 if scales[i - 1][1] == 1 else kernel_size[ratio_h - 1]            kernel_size_w = 1 if scales[i - 1][2] == 1 else kernel_size[ratio_w - 1]            fpn.append(nn.Sequential(                nn.Conv2d(scales[i - 1][0], scales[i][0], (kernel_size_h, kernel_size_w), (ratio_h, ratio_w),                          ((kernel_size_h - 1) // 2, (kernel_size_w - 1) // 2)),                nn.BatchNorm2d(scales[i][0]),                nn.ReLU(inplace=True),            ))        self.fpn = nn.Sequential(*fpn)        assert depth % 2 == 0, "the depth of CAM must be a even number"        c, h, w = scales[-1]        strides = []        conv_kernel_sizes = []        deconv_kernel_sizes = []        for i in range(depth // 2):            stride = [2] if 2 ** (depth / 2 - i) <= h else [1]            stride = stride + [2] if 2 ** (depth / 2 - i) <= w else stride + [1]            strides.append(stride)            conv_kernel_sizes.append([3, 3])            deconv_kernel_sizes.append([item ** 2 for item in stride])        convs = [nn.Sequential(            nn.Conv2d(c, num_channels, tuple(conv_kernel_sizes[0]), tuple(strides[0]),                      ((conv_kernel_sizes[0][0] - 1) // 2, (conv_kernel_sizes[0][1] - 1) // 2)),            nn.BatchNorm2d(num_channels),            nn.ReLU(inplace=True),        )]        for i in range(1, depth // 2):            convs.append(                nn.Sequential(                    nn.Conv2d(num_channels, num_channels, tuple(conv_kernel_sizes[i]), tuple(strides[i]),                              ((conv_kernel_sizes[i][0] - 1) // 2, (conv_kernel_sizes[i][1] - 1) // 2)),                    nn.BatchNorm2d(num_channels),                    nn.ReLU(inplace=True),                )            )        self.convs = nn.Sequential(*convs)        deconvs = []        for i in range(1, depth // 2):            deconvs.append(nn.Sequential(                nn.ConvTranspose2d(num_channels, num_channels, tuple(deconv_kernel_sizes[depth // 2 - i]),                                   tuple(strides[depth // 2 - i]),                                   (int(deconv_kernel_sizes[int(depth / 2) - i][0] / 4.),                                    int(deconv_kernel_sizes[int(depth / 2) - i][1] / 4.))),                nn.BatchNorm2d(num_channels),                nn.ReLU(inplace=True),            ))        deconvs.append(nn.Sequential(            nn.ConvTranspose2d(num_channels, maxT, tuple(deconv_kernel_sizes[0]), tuple(strides[0]),                               (int(deconv_kernel_sizes[0][0] / 4.), int(deconv_kernel_sizes[0][1] / 4.))),            nn.Sigmoid()        ))        self.deconvs = nn.Sequential(*deconvs)    def forward(self, input_):        x = input_[0]        for i in range(len(self.fpn)):            x = self.fpn[i](x) + input_[i + 1]        # x shape [N, 512, 8, 32]        conv_features = []        for i in range(len(self.convs)):            x = self.convs[i](x)            conv_features.append(x)        # x shape [N, 64, 1, 2]        for i in range(len(self.deconvs) - 1):            x = self.deconvs[i](x)            x = x + conv_features[len(conv_features) - 2 - i]        x = self.deconvs[-1](x)        return xclass DTD(nn.Module):    def __init__(self, num_class, num_channels, dropout=0.3):        super(DTD, self).__init__()        self.num_class = num_class        self.num_channels = num_channels        # nn.LSTM(input_size, hidden_size, num_layers), output_shape (seq_len, batch, num_directions * hidden_size)        self.pre_lstm = nn.LSTM(num_channels, num_channels // 2, bidirectional=True)        # nn.GRUCell() 参数同上， 输出 (batch, hidden_size)        self.rnn = nn.GRUCell(num_channels * 2, num_channels)        self.generator = nn.Sequential(            nn.Dropout(p=dropout),            nn.Linear(num_channels, num_class),        )        # torch.nn.Parameter是继承自torch.Tensor的子类，其主要作用是作为nn.Module中的可训练参数使用        self.char_embeddings = Parameter(torch.randn(num_class, num_channels))    def forward(self, feature, attention_map, text, text_length, test=False):        """这个 text_length 比如说 batch 为2，这两个数据都为 4 个字母, 那么 text_length具体 为 [5, 5], text 的 shape [2, 5] 的具体的数"""        batch, num_channel, height, width = feature.size()    # [N, 512, 8, 32]        num_times = attention_map.size()[1]  # [N, maxT, h, w] ---> [N, 25, 8, 32]        # normalize        attention_map = attention_map / attention_map.view(batch, num_times, -1).sum(axis=2).view(batch, num_times, 1, 1)        # weight sum        # C shape [N, 25, 512, 8, 32]        C = feature.view(batch, 1, num_channel, height, width) * attention_map.view(batch, num_times, 1, height, width)        # C shape [25, N, 512]        C = C.view(batch, num_times, num_channel, -1).sum(axis=3).transpose(1, 0)        # C shape [25, N, 512]        C, _ = self.pre_lstm(C)        C = F.dropout(C, p=0.3, training=self.training)        if not test:            len_text = int(text_length.sum())            num_steps = int(text_length.max())            gru_res = torch.zeros(C.size()).type_as(C.data)            out_res = torch.zeros(len_text, self.num_class).type_as(feature.data)            out_attentions = torch.zeros(len_text, height, width).type_as(attention_map.data)            hidden = torch.zeros(batch, self.num_channels).type_as(C.data)            prev_emb = self.char_embeddings.index_select(0, torch.zeros(batch).long().type_as(text.data))            for i in range(num_steps):                # prev_emb 为之前结果的 embedding vector                hidden = self.rnn(torch.cat((C[i, ::], prev_emb), dim=1), hidden)                gru_res[i, ::] = hidden                prev_emb = self.char_embeddings.index_select(0, text[:, i])            gru_res = self.generator(gru_res)   # classify            start = 0            for i in range(batch):                cur_length = int(text_length[i])                out_res[start: start + cur_length] = gru_res[0: cur_length, i, :]                out_attentions[start: start + cur_length] = attention_map[i, 0: cur_length, ::]                start += cur_length            return out_res, out_attentions        else:            len_text = num_times            num_steps = num_times            out_res = torch.zeros(len_text, batch, self.num_class).type_as(feature.data)            hidden = torch.zeros(batch, self.num_channels).type_as(C.data)            prev_emb = self.char_embeddings.index_select(0, torch.zeros(batch).long().type_as(text.data))            out_length = torch.zeros(batch)            now_step = 0            while 0 in out_length and now_step < num_steps:                hidden = self.rnn(torch.cat((C[now_step, ::], prev_emb), dim=1), hidden)                temp_res = self.generator(hidden)                out_res[now_step] = temp_res                temp_res = temp_res.topk(1)[1].squeeze()                for i in range(batch):                    if int(out_length[i]) == 0 and temp_res[i] == 0:                        out_length[i] = now_step + 1                prev_emb = self.char_embeddings.index_select(0, temp_res)                now_step += 1            for i in range(batch):                if int(out_length[i]) == 0:                    out_length[i] = num_steps            start = 0            output = torch.zeros(int(out_length.sum()), self.num_class).type_as(feature.data)            for i in range(batch):                cur_length = int(out_length[i])                output[start: start + cur_length] = out_res[0: cur_length, i, :]                start += cur_length            return output, out_length