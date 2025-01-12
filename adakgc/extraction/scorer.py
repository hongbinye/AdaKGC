#!/usr/bin/env python
# -*- coding:utf-8 -*-
from collections import defaultdict
from copy import deepcopy
from typing import Dict, List
import sys



def tuple_offset(offset):
    if isinstance(offset, tuple):
        return offset
    else:
        return tuple(offset)


class Metric:
    """ Tuple Metric """
    def __init__(self, verbose=False, match_mode='normal'):
        self.tp = 0.              
        self.gold_num = 0.        
        self.pred_num = 0.        
        self.verbose = verbose
        self.match_mode = match_mode
        assert self.match_mode in {'set', 'normal', 'multimatch'}

    def __repr__(self) -> str:
        return f"tp: {self.tp}, gold: {self.gold_num}, pred: {self.pred_num}"

    @staticmethod
    def safe_div(a, b):
        if b == 0.:
            return 0.
        else:
            return a / b

    def compute_f1(self, prefix=''):
        tp = self.tp
        pred_num = self.pred_num
        gold_num = self.gold_num
        p, r = self.safe_div(tp, pred_num), self.safe_div(tp, gold_num)
        return {prefix + 'tp': tp,
                prefix + 'gold': gold_num,
                prefix + 'pred': pred_num,
                prefix + 'P': p * 100,
                prefix + 'R': r * 100,
                prefix + 'F1': self.safe_div(2 * p * r, p + r) * 100
                }

    def count_instance(self, gold_list, pred_list):
        if self.match_mode == 'set':
            gold_list = set(gold_list)
            pred_list = set(pred_list)
            if self.verbose:
                print("Gold:", gold_list)
                print("Pred:", pred_list)
            self.gold_num += len(gold_list)
            self.pred_num += len(pred_list)
            self.tp += len(gold_list & pred_list)

        else:
            if self.verbose:
                print("Gold:", gold_list)
                print("Pred:", pred_list)
            self.gold_num += len(gold_list)
            self.pred_num += len(pred_list)

            if len(gold_list) > 0 and len(pred_list) > 0:
                # guarantee length same
                assert len(gold_list[0]) == len(pred_list[0])

            dup_gold_list = deepcopy(gold_list)
            for pred in pred_list:
                if pred in dup_gold_list:
                    self.tp += 1
                    if self.match_mode == 'normal':
                        # Each Gold Instance can be matched one time
                        dup_gold_list.remove(pred)

    def count_batch_instance(self, batch_gold_list, batch_pred_list):
        for gold_list, pred_list in zip(batch_gold_list, batch_pred_list):
            self.count_instance(gold_list=gold_list, pred_list=pred_list)


class RecordMetric(Metric):
    """ 不考虑不同 Role 之间的顺序，例如事件论元"""
    @staticmethod
    def is_equal(gold, pred):
        if gold['type'] != pred['type']:
            return False
        if gold['spot'] != pred['spot']:
            return False
        if len(gold['asocs']) != len(pred['asocs']):
            return False
        for gold_role, pred_role in zip(sorted(gold['asocs']), sorted(pred['asocs'])):
            if gold_role != pred_role:
                return False
        return True

    def count_instance(self, gold_list, pred_list):
        if self.match_mode == 'set':
            raise NotImplementedError(f'{self.__class__.__name__} do not support the match model `set`')

        if self.verbose:
            print("Gold:", gold_list)
            print("Pred:", pred_list)

        self.gold_num += len(gold_list)
        self.pred_num += len(pred_list)

        gold_indexes = list(range(len(gold_list)))
        non_found = [True] * len(gold_list)
        for pred in pred_list:
            for gold_index in gold_indexes:
                if non_found[gold_index] and self.is_equal(gold_list[gold_index], pred):
                    self.tp += 1
                    non_found[gold_index] = False
                    if self.match_mode == 'normal':
                        break


class OrderedRecordMetric(RecordMetric):
    """ 考虑不同 Role 之间的顺序，例如关系 """
    @staticmethod
    def is_equal(gold, pred):
        if gold['type'] != pred['type']:
            return False
        if gold['spot'] != pred['spot']:
            return False
        if len(gold['asocs']) != len(pred['asocs']):
            return False
        for gold_role, pred_role in zip(gold['asocs'], pred['asocs']):
            if gold_role != pred_role:
                return False
        return True


def warning_tp_increment(gold, pred, prefix):
    sys.stderr.write(f"{prefix} TP Increment Warning, Gold Offset: {gold['offset']}\n")
    sys.stderr.write(f"{prefix} TP Increment Warning, Pred Offset: {pred['offset']}\n")
    sys.stderr.write(f"{prefix} TP Increment Warning, Gold String: {gold['string']}\n")
    sys.stderr.write(f"{prefix} TP Increment Warning, Pred String: {pred['string']}\n")
    sys.stderr.write(f"===============\n")


class Scorer:
    @staticmethod
    def load_gold_list(gold_list, offset_key=None):
        raise NotImplementedError

    @staticmethod
    def load_pred_list(pred_list):
        raise NotImplementedError

    @staticmethod
    def eval_instance_list(gold_instance_list, pred_instance_list, verbose=False, match_mode='normal'):
        raise NotImplementedError



class EntityScorer(Scorer):
    @staticmethod
    def load_gold_list(gold_list: List[List[Dict]]):
        gold_instance_list = []
        for gold in gold_list:
            gold_offset = list()
            gold_string = list()
            for span in gold:
                span_label = span['type']
                span_offset = span['offset']
                span_text = span['text']
                gold_offset += [(span_label, tuple_offset(span_offset))]
                gold_string += [(span_label, span_text)]
            gold_instance = {
                'offset': gold_offset,
                'string': gold_string,
            }
            gold_instance_list += [gold_instance]
        return gold_instance_list


    @staticmethod
    def load_pred_list(pred_list: List[Dict]):
        pred_instance_list = list()
        for pred in pred_list:
            for offset_pred in pred['offset']:
                if not isinstance(offset_pred[1], tuple):
                    offset_pred[1] = tuple_offset(offset_pred[1])
            pred['offset'] = [tuple_offset(p) for p in pred['offset']]
            pred['string'] = [tuple_offset(p) for p in pred['string']]
            pred_instance_list += [pred]
        return pred_instance_list


    @staticmethod
    def eval_instance_list(gold_instance_list: List[Dict], pred_instance_list: List[Dict], verbose=False, match_mode='normal'):
        metrics = {
            'string': Metric(verbose=verbose, match_mode=match_mode),
            'offset': Metric(verbose=verbose, match_mode=match_mode),
        }
        for pred, gold in zip(pred_instance_list, gold_instance_list):

            pre_string_tp, pre_offset_tp = metrics['string'].tp, metrics['offset'].tp

            for eval_key in metrics:
                metrics[eval_key].count_instance(
                    gold_list=gold.get(eval_key, []),
                    pred_list=pred.get(eval_key, [])
                )

            post_string_tp, post_offset_tp = metrics['string'].tp, metrics['offset'].tp
            if verbose and post_offset_tp - pre_offset_tp != post_string_tp - pre_string_tp:
                warning_tp_increment(gold=gold, pred=pred, prefix='Entity')

        results = dict()
        for eval_key in metrics:
            results.update(metrics[eval_key].compute_f1(prefix=eval_key + '-ent-'))

        return results




class RelationScorer(Scorer):
    @staticmethod
    def load_gold_list(gold_list: List[List[Dict]]):
        gold_instance_list = []
        for gold in gold_list:
            gold_instance = defaultdict(list)
            for record in gold:
                assert len(record['args']) == 2
                gold_instance['offset'] += [(
                    record['type'],
                    record['args'][0]['type'],
                    tuple_offset(record['args'][0]['offset']),
                    record['args'][1]['type'],
                    tuple_offset(record['args'][1]['offset']),
                )]
                gold_instance['string'] += [(
                    record['type'],
                    record['args'][0]['type'],
                    record['args'][0]['text'],
                    record['args'][1]['type'],
                    record['args'][1]['text'],
                )]
            gold_instance_list += [gold_instance]

        return gold_instance_list


    @staticmethod
    def load_pred_list(pred_list):
        pred_instance_list = list()
        for pred in pred_list:
            for offset_pred in pred['offset']:

                if not isinstance(offset_pred[2], tuple):
                    offset_pred[2] = tuple_offset(offset_pred[2])

                if not isinstance(offset_pred[4], tuple):
                    offset_pred[4] = tuple_offset(offset_pred[4])

            pred['offset'] = [tuple_offset(p) for p in pred['offset']]
            pred['string'] = [tuple_offset(p) for p in pred['string']]
            pred_instance_list += [pred]
        return pred_instance_list


    @staticmethod
    def eval_instance_list(gold_instance_list, pred_instance_list, verbose=False, match_mode='normal'):
        # Span Boundary and Type
        metrics = {
            'offset': Metric(verbose=verbose, match_mode=match_mode),
            'string': Metric(verbose=verbose, match_mode=match_mode),
        }
        # Span Boundary Only    不看标签是否正确，只看句子中对应的Span是否正确
        boundary_metrics = {
            'offset': Metric(verbose=verbose, match_mode=match_mode),
            'string': Metric(verbose=verbose, match_mode=match_mode),
        }
        for pred, gold in zip(pred_instance_list, gold_instance_list):

            pre_string_tp, pre_offset_tp = metrics['string'].tp, metrics['offset'].tp

            for eval_key in metrics:
                # Span Boundary and Type
                metrics[eval_key].count_instance(
                    gold_list=gold.get(eval_key, []),
                    pred_list=pred.get(eval_key, []),
                )

            post_string_tp, post_offset_tp = metrics['string'].tp, metrics['offset'].tp
            if verbose and (post_offset_tp - pre_offset_tp != post_string_tp - pre_string_tp):
                warning_tp_increment(gold=gold, pred=pred, prefix='Relation Strict')

            pre_string_tp, pre_offset_tp = boundary_metrics['string'].tp, boundary_metrics['offset'].tp

            for eval_key in boundary_metrics:
                # Span Boundary Only
                boundary_metrics[eval_key].count_instance(
                    gold_list=[(x[0], x[2], x[4]) for x in gold.get(eval_key, [])],
                    pred_list=[(x[0], x[2], x[4]) for x in pred.get(eval_key, [])],
                )
            post_string_tp, post_offset_tp = boundary_metrics['string'].tp, boundary_metrics['offset'].tp
            if verbose and post_offset_tp - pre_offset_tp != post_string_tp - pre_string_tp:
                warning_tp_increment(gold=gold, pred=pred, prefix='Relation Boundary')

        results = dict()
        for eval_key in metrics:
            results.update(metrics[eval_key].compute_f1(prefix=eval_key + '-rel-strict-'))
        for eval_key in boundary_metrics:
            results.update(boundary_metrics[eval_key].compute_f1(prefix=eval_key + '-rel-boundary-'))
        return results


class EventScorer(Scorer):
    @staticmethod
    def load_gold_list(gold_list):
        gold_instance_list = []
        for gold in gold_list:
            gold_instance = defaultdict(list)
            for record in gold:
                gold_instance['offset_trigger'] += [(record['type'], tuple_offset(record['offset']))]
                gold_instance['string_trigger'] += [(record['type'], record['text'])]
                for arg in record['args']:
                    gold_instance['offset_role'] += [(record['type'], arg['type'], tuple_offset(arg['offset']))]
                    gold_instance['string_role'] += [(record['type'], arg['type'], arg['text'])]
            gold_instance_list += [gold_instance]
        return gold_instance_list


    @staticmethod
    def load_pred_list(pred_list):
        pred_instance_list = list()
        for pred in pred_list:
            pred_instance = defaultdict(list)

            for offset_pred in pred['offset']:
                event_type, trigger_offset = offset_pred['type'], tuple_offset(offset_pred['trigger'])
                pred_instance['offset_trigger'] += [(event_type, trigger_offset)]
                for role_type, role_offset in offset_pred['roles']:
                    pred_instance['offset_role'] += [(event_type, role_type, tuple_offset(role_offset))]

            for string_pred in pred['string']:
                event_type, trigger_string = string_pred['type'], string_pred['trigger']
                pred_instance['string_trigger'] += [(event_type, trigger_string)]
                for role_type, role_string in string_pred['roles']:
                    pred_instance['string_role'] += [(event_type, role_type, role_string)]
            pred_instance_list += [pred_instance]
        return pred_instance_list


    @staticmethod
    def eval_instance_list(gold_instance_list, pred_instance_list, verbose=False, match_mode='normal'):
        trigger_metrics = {
                'offset': Metric(verbose=verbose, match_mode=match_mode),
                'string': Metric(verbose=verbose, match_mode=match_mode),
        }
        role_metrics = {
                'offset': Metric(verbose=verbose, match_mode=match_mode),
                'string': Metric(verbose=verbose, match_mode=match_mode),
        }

        for pred, gold in zip(pred_instance_list, gold_instance_list):

            pre_string_tp, pre_offset_tp = trigger_metrics['string'].tp, trigger_metrics['offset'].tp

            for eval_key in trigger_metrics:
                trigger_metrics[eval_key].count_instance(
                    gold_list=gold.get(eval_key + '_trigger', []),
                    pred_list=pred.get(eval_key + '_trigger', [])
                )

            post_string_tp, post_offset_tp = trigger_metrics['string'].tp, trigger_metrics['offset'].tp
            if verbose and post_offset_tp - pre_offset_tp != post_string_tp - pre_string_tp:
                warning_tp_increment(gold=gold, pred=pred, prefix='Trigger')

            pre_string_tp, pre_offset_tp = role_metrics['string'].tp, role_metrics['offset'].tp

            for eval_key in role_metrics:
                role_metrics[eval_key].count_instance(
                    gold_list=gold.get(eval_key + '_role', []),
                    pred_list=pred.get(eval_key + '_role', [])
                )

            post_string_tp, post_offset_tp = role_metrics['string'].tp, role_metrics['offset'].tp
            if verbose and post_offset_tp - pre_offset_tp != post_string_tp - pre_string_tp:
                warning_tp_increment(gold=gold, pred=pred, prefix='Role')

        results = dict()
        for eval_key in trigger_metrics:
            results.update(trigger_metrics[eval_key].compute_f1(prefix=f'{eval_key}-evt-trigger-'))
        for eval_key in role_metrics:
            results.update(role_metrics[eval_key].compute_f1(prefix=f'{eval_key}-evt-role-'))

        return results



