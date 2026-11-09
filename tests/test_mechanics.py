"""Artificial fixtures validate mechanics, never enter historical results."""
import unittest
import numpy as np
import pandas as pd
from pipeline.engine import transaction
from pipeline.allocation import band_target,allocate,tail_loss

class Accounting(unittest.TestCase):
    def test_initial_purchase_exact(self):
        v,c,d,f=transaction([0.,0.],1.,[.5,.5],.001)
        self.assertAlmostEqual(v.sum(),1/1.001)
        self.assertAlmostEqual(f,.001/1.001)
        self.assertAlmostEqual(c,0.)

    def test_two_sided_fees(self):
        v,c,d,f=transaction([1.,0.],0.,[0.,1.],.001)
        self.assertAlmostEqual(v[1],.999/1.001)
        self.assertAlmostEqual(f,.001*(1+v[1]))
        self.assertAlmostEqual(d[0],-1.)

    def test_exit_to_cash(self):
        v,c,d,f=transaction([.4,.6],0.,[0.,0.],.001)
        self.assertAlmostEqual(c,.999)
        self.assertAlmostEqual(v.sum(),0.)

    def test_buy_and_sell_cash_identity_random(self):
        rng=np.random.default_rng(4517)
        for _ in range(100):
            old=rng.dirichlet(np.ones(8));target=rng.dirichlet(np.ones(8))
            v,c,d,f=transaction(old[:7],old[7],target[:7],.0025)
            self.assertAlmostEqual(v.sum()+c+f,1.)
            self.assertAlmostEqual(old[7]-d.sum()-f,c)

class Allocation(unittest.TestCase):
    def setUp(self):
        self.names=list('ABCDEFGH')
        rng=np.random.default_rng(451)
        self.R=pd.DataFrame(rng.normal(.005,.03,(60,8)),columns=self.names)

    def test_inside_bands_does_not_trade(self):
        target=pd.Series(.125,index=self.names)
        current=target.copy();current.iloc[0]+=.01;current.iloc[1]-=.01
        actual=band_target(current,target,self.R)
        np.testing.assert_allclose(actual,current)

    def test_filtered_zero_requires_full_exit(self):
        current=pd.Series(.125,index=self.names)
        target=current.copy();target.iloc[0]=0.
        actual=band_target(current,target,self.R)
        self.assertAlmostEqual(actual.iloc[0],0.)
        self.assertAlmostEqual(actual.sum(),.875)
        self.assertLessEqual(abs(actual-target).max(),.030001)

    def test_zero_band_executes_exact_target(self):
        current=pd.Series(0.,index=self.names)
        target=pd.Series(.125,index=self.names)
        np.testing.assert_allclose(band_target(current,target,self.R,band=0.),target,atol=1e-7)

    def test_optimizer_caps_and_funding(self):
        weight,diag=allocate(self.R,.02,pd.Series(dtype=float))
        self.assertAlmostEqual(weight.sum(),1.)
        self.assertGreaterEqual(weight.min(),0.)
        self.assertLessEqual(weight.max(),.200002)
        self.assertLessEqual(diag['cvar95_monthly'],.150002)

    def test_negative_excess_has_explicit_minimum_risk_fallback(self):
        weight,diag=allocate(self.R-.10,.20,pd.Series(dtype=float))
        self.assertEqual(diag['method'],'negative_expected_excess_minimum_risk')
        self.assertAlmostEqual(weight.sum(),1.)

    def test_empirical_cvar_matches_three_worst_of_sixty(self):
        returns=np.arange(60)/1000-.04
        self.assertAlmostEqual(tail_loss(returns[:,None],[1.]),-returns[:3].mean())

if __name__=='__main__':unittest.main()
