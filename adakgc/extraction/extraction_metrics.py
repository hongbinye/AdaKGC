#!/usr/bin/env python
# -*- coding:utf-8 -*-
from typing import List
from adakgc.utils.record_schema import RecordSchema
from adakgc.extraction.predict_parser import SpotAsocPredictParser
from adakgc.extraction.scorer import Metric, RecordMetric, OrderedRecordMetric


def eval_pred(predict_parser: SpotAsocPredictParser, gold_list, pred_list, text_list=None, raw_list=None):
    well_formed_list, counter = predict_parser.decode(
        gold_list, pred_list, text_list, raw_list
    )

    spot_metric = Metric()
    asoc_metric = Metric()
    record_metric = RecordMetric()
    ordered_record_metric = OrderedRecordMetric()

    for instance in well_formed_list:
        spot_metric.count_instance(instance['gold_spot'], instance['pred_spot'])
        asoc_metric.count_instance(instance['gold_asoc'], instance['pred_asoc'])
        record_metric.count_instance(instance['gold_record'], instance['pred_record'])
        ordered_record_metric.count_instance(instance['gold_record'], instance['pred_record'])

    spot_result = spot_metric.compute_f1(prefix='spot-')
    asoc_result = asoc_metric.compute_f1(prefix='asoc-')
    record_result = record_metric.compute_f1(prefix='record-')
    ordered_record_result = ordered_record_metric.compute_f1(prefix='ordered-record-')

    overall_f1 = spot_result.get('spot-F1', 0.) + asoc_result.get('asoc-F1', 0.)
   
    result = {'overall-F1': overall_f1}
    result.update(spot_result)
    result.update(asoc_result)
    result.update(record_result)
    result.update(ordered_record_result)
    result.update(counter)
    return result


def get_extract_metrics(pred_lns: List[str], tgt_lns: List[str], label_constraint: RecordSchema):
    predict_parser = SpotAsocPredictParser(label_constraint=label_constraint)
    return eval_pred(
        predict_parser=predict_parser,
        gold_list=tgt_lns,
        pred_list=pred_lns
    )
