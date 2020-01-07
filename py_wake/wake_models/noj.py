from py_wake.wake_model import WakeModel, SquaredSum
import numpy as np
from numpy import newaxis as na


class AreaOverlappingFactor():
    def __init__(self, k=.1):
        self.k = k

    def overlapping_area_factor(self, dw_jl, cw_jl, D_src_l, D_dst_jl):
        """Calculate overlapping factor

        Parameters
        ----------
        dw_jl : array_like
            down wind distance [m]
        cw_jl : array_like
            cross wind distance [m]
        D_src_l : array_like
            Diameter of source turbines [m]
        D_dst_jl : array_like or None
            Diameter of destination turbines [m]. If None destination is assumed to be a point

        Returns
        -------
        A_ol_factor_jl : array_like
            area overlaping factor
        """
        wake_radius_jl = (self.k * dw_jl + D_src_l[na, :] / 2)
        if D_dst_jl is None:
            return wake_radius_jl > cw_jl
        else:
            return self.cal_overlapping_area_factor(wake_radius_jl,
                                                    (D_dst_jl / 2),
                                                    np.abs(cw_jl))

    def cal_overlapping_area_factor(self, R1, R2, d):
        """ Calculate the overlapping area of two circles with radius R1 and
        R2, centers distanced d.

        The calculation formula can be found in Eq. (A1) of :
        [Ref] Feng J, Shen WZ, Solving the wind farm layout optimization
        problem using Random search algorithm, Reneable Energy 78 (2015)
        182-192
        Note that however there are typos in Equation (A1), '2' before alpha
        and beta should be 1.

        Parameters
        ----------
        R1: array:float
            Radius of the first circle [m]

        R2: array:float
            Radius of the second circle [m]

        d: array:float
            Distance between two centers [m]

        Returns
        -------
        A_ol: array:float
            Overlapping area [m^2]
        """
        # treat all input as array
        R1, R2, d = np.array(R1), np.array(R2), np.array(d),
        A_ol_f = np.zeros_like(R1)
        p = (R1 + R2 + d) / 2.0

        # make sure R_big >= R_small
        Rmax = np.where(R1 < R2, R2, R1)
        Rmin = np.where(R1 < R2, R1, R2)

        # full wake cases
        index_fullwake = (d <= (Rmax - Rmin))
        A_ol_f[index_fullwake] = 1

        # partial wake cases
        mask = (d > (Rmax - Rmin)) & (d < (Rmin + Rmax))

        # in somecases cos_alpha or cos_beta can be larger than 1 or less than
        # -1.0, cause problem to arccos(), resulting nan values, here fix this
        # issue.
        def arccos_lim(x):
            return np.arccos(np.maximum(np.minimum(x, 1), -1))

        alpha = arccos_lim((Rmax[mask]**2.0 + d[mask]**2 - Rmin[mask]**2) /
                           (2.0 * Rmax[mask] * d[mask]))

        beta = arccos_lim((Rmin[mask]**2.0 + d[mask]**2 - Rmax[mask]**2) /
                          (2.0 * Rmin[mask] * d[mask]))

        A_triangle = np.sqrt(p[mask] * (p[mask] - Rmin[mask]) *
                             (p[mask] - Rmax[mask]) * (p[mask] - d[mask]))

        A_ol_f[mask] = (alpha * Rmax[mask]**2 + beta * Rmin[mask]**2 -
                        2.0 * A_triangle) / (R2[mask]**2 * np.pi)

        return A_ol_f


class NOJ(SquaredSum, WakeModel, AreaOverlappingFactor):
    args4deficit = ['WS_lk', 'D_src_l', 'D_dst_jl', 'dw_jl', 'cw_jl', 'ct_lk']

    def __init__(self, site, windTurbines, k=.1, **kwargs):
        WakeModel.__init__(self, site, windTurbines, **kwargs)
        AreaOverlappingFactor.__init__(self, k)

    def calc_deficit(self, WS_lk, D_src_l, D_dst_jl, dw_jl, cw_jl, ct_lk):

        # Calculate the wake loss using NOJ
        # Jensen, Niels Otto. "A note on wind generator interaction." (1983)
        # V_def = v*(1-sqrt(1-Ct))/(1+k*dist_down/R)**2

        R_src_l = D_src_l / 2

        term_denominator_jl = (1 + self.k * dw_jl / R_src_l[na, :])**2

        A_ol_factor_jl = self.overlapping_area_factor(dw_jl, cw_jl, D_src_l, D_dst_jl)
        ct_lk = np.minimum(ct_lk, 1)   # treat ct_lk for np.sqrt()
        term_numerator_lk = WS_lk * (1 - np.sqrt(1 - ct_lk))
        with np.warnings.catch_warnings():
            np.warnings.filterwarnings('ignore', r'invalid value encountered in true_divide')
            deficit_jlk = term_numerator_lk[na] * (A_ol_factor_jl / term_denominator_jl)[:, :, na]
        return deficit_jlk


def main():
    if __name__ == '__main__':
        from py_wake.aep_calculator import AEPCalculator
        from py_wake.examples.data.iea37 import iea37_path
        from py_wake.examples.data.iea37._iea37 import IEA37Site
        from py_wake.examples.data.iea37._iea37 import IEA37_WindTurbines

        # setup site, turbines and wakemodel
        site = IEA37Site(16)
        x, y = site.initial_position.T
        windTurbines = IEA37_WindTurbines()

        wake_model = NOJ(site, windTurbines)

        # calculate AEP
        aep_calculator = AEPCalculator(wake_model)
        aep = aep_calculator.calculate_AEP(x, y)[0].sum()

        # plot wake mape
        import matplotlib.pyplot as plt
        aep_calculator.plot_wake_map(wt_x=x, wt_y=y, wd=[0], ws=[9])
        plt.title('AEP: %.2f GWh' % aep)
        windTurbines.plot(x, y)
        plt.show()


main()
