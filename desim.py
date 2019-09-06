"""
DEshima SIMulator.
Module for calculating the sensitivity of a DESHIMA-type spectrometer.

FAQ
-----
Q.  Where is the factor 2 of polarization loss included ?
        A.  In eta_source_window()
Q.  Where is the point-source coupling phase and amplitude loss
    due to the mismatch between the
    beam in radiation and reception, that Shahab calculates
    at the lens surface?
        A.  It is included in the main beam efficiency.
            These losses reduce the coupling to a point source,
            but the power (in transmission) couples to the sky.
"""

import numpy as np
import matplotlib.pyplot as plt
from scipy import integrate
import copy
import pandas as pd
import os
from scipy.interpolate import interp2d
from matplotlib.backends.backend_pdf import PdfPages
import sys

h = 6.62607004 * 10**-34  # Planck constant
k = 1.38064852 * 10**-23  # Boltzmann constant
e = 1.60217662 * 10**-19  # electron charge
c = 299792458.  # velocity of light
Delta_Al = 188 * 10**-6 * e  # gap energy of Al
eta_pb = 0.4  # Pair breaking efficiency

# Ohmic loss of an Al surface.
# Shitov et al., ISSTT2008
# https://www.nrao.edu/meetings/isstt/papers/2008/2008263266.pdf
Al_refl_ohmic_loss = 0.9975


def spectrometer_sensitivity(
        F=350.*10.**9.,  # Hz, scalar or vector
        pwv=0.5,  # mm, scalar
        EL=60.,  # deg, scalar
        R=500,  # scalar. R = Q = F/FWHM = F/dF is assumed.
        eta_M1_spill=0.99,  # scalar or vector
        eta_M2_spill=0.90,  # scalar or vector
        eta_wo=0.99,  # scalar or vector. product of all cabin loss
        window_AR=True,
        # scalar or vector. product of co spillover, qo filter transmission
        eta_co=0.65,
        # scalar or vector. D2_2V3.pdf, p14:
        # front-to-back ratio 0.93 * reflection efficiency 0.9
        # * matching 0.98 * antenna spillover 0.993
        eta_lens_antenna_rad=0.81,
        # scalar or vector. 'Alejandro Efficiency',
        # from the feedpoint of the antenna to being absorbed in the KID.
        eta_circuit=0.32,
        eta_IBF=0.6,
        KID_excess_noise_factor = 1.1,
        theta_maj=22. * np.pi / 180. / 60. / 60.,  # scalar or vector.
        theta_min=22. * np.pi / 180. / 60. / 60.,  # scalar or vector.
        eta_mb=0.6,  # scalar or vector.
        telescope_diameter=10.,
        Tb_cmb=2.725,
        Tp_amb=273.,
        Tp_cabin=290.,
        Tp_co=4.,
        Tp_chip=0.12,
        snr=5.,
        obs_hours=10.,
        on_source_fraction=0.4,
        on_off = True
        ):
    """
    Calculate the sensitivity of a spectrometer.

    Parameters
    ------------
    One of the parameters can be a vector of length N.
    In this case the output of the script will be a 2D pandas.DataFrame
    with N rows.
    If all parameters are a scalar, then the output will be
    a 1D pandas DataFrame (or Series?)

    F : scalar or vector
        Frequency of the astronomical signal.
        Unit: Hz
    pwv : scalar or vector
        precipitable water vapour.
        Unit: mm
    EL : scalar or vector
        telescope elevation angle
        Unit: degrees
    R : scalar or vector
        spectral resolving power in F/W_F
        W_F is the 'equivalent bandwidth'
            http://www.astrosurf.com/buil/us/spe2/hresol7.htm
        Unit : None.
    eta_M1_spill : scalar or vector
        spillover efficiency at the telescope primary mirror.
        Unit: None.
    eta_M2_spill : scalar or vector
        spillover efficiency at the telescope secondary mirror.
        Unit: None.
    eta_wo : scalar or vector
        Product of all losses in the warm optics in the cabin.
        This includes:
            - Spillover losses
            - Ohmic losses
        Unit: None.
    eta_co : scalar or vector
        Product of following:
            - Cold spillover
            - Cold ohmic losses
            - Filter transmission loss
        Unit: None.
    eta_lens_antenna_rad : scalar or vector
        The loss at chip temperature, *that is not in the circuit.*
        Product of the following:
            - Front-to-back ratio of the lens-antenna on the chip.
            - Reflection efficiency at the surface of the lens.
            - Matching efficiency, due to the mismatch
            - Spillover efficiency of the lens-antenna
        These values can be found in D2_2V3.pdf, p14
        Unit: None.
    eta_circuit : scalar or vector
        The loss at chip temperature, *in the circuit.*
        Unit: None.
    eta_IBF : in-band fraction efficiency
        Fraction of the filter power transmission that is
        within the filter channel bandwidth.
        The rest of the power is cross talk,
        picking up power that is in the bands of neighboring channels.
        This efficiency applies to the coupling to astronomical line signals.
        This efficiency does not apply to the coupling to continuum,
        including the the coupling to the atmosphere for calculating the NEP.
    theta_maj : scalar or vector
        The HPBW along the major axis, assuming a Gaussian beam.
        Unit: radians.
    theta_min : scalar or vector
        The HPBW along the minor axis, assuming a Gaussian beam.
        Unit: radians.
    eta_mb : scalar or vector
        main beam efficiency.
        Note that eta_mb includes the following terms from D2_2V3.pdf
        from Shahab's report.
            - eta_Phi
            - eta_amp
        Because a decrease in these will launch the beam to the sky b
        ut not couple it to the point source.
        (See also FAQ.)
        Unit: None.
    telescope_diameter : float or vector.
        diameter of the telescope.
        Units: m
    Tb_cmb : scalar or vector
        Brightness temperature of the CMB.
        Unit: K
    Tp_amb : scalar or vector
        Physical temperature of the atmosphere and ambient environment
        around the telescope.
        Unit: K
    Tp_cabin : scalar or vector
        Physical temperature of the telescope cabin.
        Unit: K
    Tp_co : scalar or vector
        Physical temperature of the cold optics inside the cryostat.
        Unit: K
    Tp_chip : scalar or vector
        Physical temperature of the chip.
        Unit: K
    snr : scalar or vector
        target signal to noise to be reached. (for calculating the MDLF)
        Unit: None.
    obs_hours :  scalar or vector
        observing hours, including off-source time and the slew
        overhead between on- and off-source.
        Unit : hours
    on_source_fraction : scalar or vector
        Fraction of the time on source (between 0. and 1.)
    on_off: True or False
        If the observation involves on_off chopping, then the SNR degrades by sqrt(2) because
        the signal difference includes the noise twice. 

    Returns
    ----------
    The function returns one pandas.DataFrame called 'result',
    which contains the following rows that are all pandas.Series
    F : same as input
    pwv : same as input
    EL : same as input
    eta_atm : atmospheric transmission. Unit: None
    R : same as input
    W_F_spec : equivalent bandwidth within the bandwidth of F/R. Units: Hz
    W_F_cont : equivalent bandwidth of 1 channel including
        the power coupled outside of the filter channel band.
        Units: Hz
    theta_maj : same as input.
    theta_min : same as input.
    eta_a : aperture efficiency (https://deshima.kibe.la/notes/324)
    eta_mb : main beam efficiency
    eta_forward : forward efficiency (https://deshima.kibe.la/notes/324)
    eta_sw : coupling efficiency from a point source to the cryostat window
    eta_window : transmission of the cryostat window
    eta_inst : instrument optical efficiency (https://arxiv.org/abs/1901.06934)
    eta_circuit : same as input
    Tb_sky : Callen-Welton brightness temperature of the sky. Units : K
    Tb_M1 : Callen-Weltonbrightness temperature looking
            into the telescope primary. Units: K
    Tb_M2 :
        Callen-Welton brightness temperature looking
        into the telescope secondary,
        including the spillover to the cold sky. Units: K
    Tb_wo : Callen-Welton brightness temperature looking into the warm optics.
        Units: K
    Tb_window : Callen-Welton brightness temperature looking into the window.
        Units: K
    Tb_co : Callen-Welton brightness temperature looking into the cold optis.
        Units: K
    Tb_KID : Callen-Welton brightness temperature looking into the filter
        _from_ the KID. Units: K
    Pkid : Power absorbed by the KID. Units: W
    n_ph : Photon occupation number. Units: None.
        (http://adsabs.harvard.edu/abs/1999ASPC..180..671R)
    NEPkid : Noise equivalent power at the KID
        with respect to the absorbed power. Units: W Hz^0.5
    NEPinst : Instrumnet NEP  Units: W Hz^0.5
        (https://arxiv.org/abs/1901.06934).
    NEFD_line : Noise Equivalent Flux Density for
        couploing to a line that is not wider than the
        filter bandwidth. Units: W/m^2/Hz * s^0.5
    NEFD_continuum : Noise Equivalent Flux Density for
        couploing to a countinuum source. Units: W/m^2/Hz * s^0.5
    NEFD_ : Noise Equivalent Flux Density for
        couploing to a countinuum source. Units: W/m^2/Hz * s^0.5
    NEF : Noise Equivalent Flux. Units: W/m^2 * s^0.5
    MDLF : Minimum Detectable Line Flux. Units: W/m^2
    snr : same as input.
    obs_hours : same as input.
    on_source_fraction : same as input.
    on_source_hours : obs_hours * obs_hours*on_source_fraction Units: None.
    equivalent_Trx :
        equivalent receiver noise temperature. Units: K
        at the moment this assumes Rayleigh-Jeans!

    Areas to improve
    ----------------
    - The parameters to calculate the window transmission / reflection
    is hard-coded in the function window_trans().

    """

    eta_M1_ohmic = Al_refl_ohmic_loss
    eta_M2_ohmic = Al_refl_ohmic_loss

    # Collect efficiencies at the same temperature
    eta_M1 = eta_M1_ohmic * eta_M1_spill
    eta_chip = eta_lens_antenna_rad * eta_circuit

    # Forward efficiency: does/should not include window loss
    eta_forward = (eta_M1*eta_M2_ohmic * eta_M2_spill * eta_wo +
                   (1.-eta_M2_spill)*eta_wo)

    # Equivalent Bandwidth of 1 channel.
    W_F_cont = F/R/eta_IBF
    W_F_spec = F/R

    # Calcuate eta. scalar/vector depending on F.
    eta_atm = eta_atm_func(F=F, pwv=pwv, EL=EL, R=R)

    # Calculate the intrinsic Johnson-Nyquist power
    # for all physical temperatures
    psd_jn_cmb = johnson_nyquist_psd(F=F, T=Tb_cmb)
    psd_jn_amb = johnson_nyquist_psd(F=F, T=Tp_amb)
    psd_jn_cabin = johnson_nyquist_psd(F=F, T=Tp_cabin)
    psd_jn_co = johnson_nyquist_psd(F=F, T=Tp_co)
    psd_jn_chip = johnson_nyquist_psd(F=F, T=Tp_chip)

    # Power density (W/Hz) at different stages
    psd_sky =       rad_trans(psd_jn_cmb,   psd_jn_amb,     eta_atm     )
    psd_M1  =       rad_trans(psd_sky,      psd_jn_amb,     eta_M1      )
    psd_M2_spill =  rad_trans(psd_M1,       psd_sky,        eta_M2_spill)
    psd_M2 =        rad_trans(psd_M2_spill, psd_jn_amb,     eta_M2_ohmic)
    psd_wo =        rad_trans(psd_M2,       psd_jn_cabin,   eta_wo      )
    if window_AR is True:
        psd_window = psd_wo
        eta_window = 1.
        HDPErefl = 0.
    else:
        [psd_window, eta_window, HDPErefl] = (
                    window_trans(F, psd_wo,    psd_jn_cabin,   psd_jn_co   ))
    psd_co =        rad_trans(psd_window,   psd_jn_co,      eta_co      )
    psd_KID =       rad_trans(psd_co,       psd_jn_chip,    eta_chip    )  # PSD absorbed by KID

    # Instrument optical efficiency
    eta_inst = eta_chip * eta_co * eta_window

    # Sky loading, for reference
    psd_KID_sky_1 = psd_sky * eta_M1 * eta_M2_spill * eta_M2_ohmic * eta_wo * eta_inst
    psd_KID_sky_2 = rad_trans(0, psd_sky, eta_M2_spill) * eta_M2_ohmic * eta_wo * eta_inst
    psd_KID_sky = psd_KID_sky_1 + psd_KID_sky_2

    # Warm loading, for reference

    psd_KID_warm =  rad_trans(
                        rad_trans(
                            rad_trans(
                                rad_trans(0, psd_jn_amb, eta_M1),
                            0, eta_M2_spill), # sky spillover does not count for warm loading
                        psd_jn_amb, eta_M2_ohmic),
                    psd_jn_cabin, eta_wo)

    if window_AR is True:
        psd_KID_warm = psd_KID_warm * eta_chip * eta_co
    else:
        psd_KID_warm =  window_trans(F,psd_KID_warm, psd_jn_cabin, psd_jn_co)[0] * eta_co * eta_chip

    # Cold loading, for reference
    psd_KID_cold =  rad_trans(
                        rad_trans(
                            # rad_trans(0,psd_jn_co,HDPErefl),
                            0,
                        psd_jn_co, eta_co),
                    psd_jn_chip, eta_chip)

    # Photon + R(ecombination) NEP
    Pkid = psd_KID * W_F_cont
    Pkid_sky = psd_KID_sky * W_F_cont
    Pkid_warm = psd_KID_warm * W_F_cont
    Pkid_cold = psd_KID_cold * W_F_cont

    NEPkid = photon_NEP_kid(F,Pkid,W_F_cont)
    NEPinst = NEPkid / eta_inst  # Instrument NEP

    eta_a = aperture_efficiency(
        F=F,
        theta_maj=theta_maj,
        theta_min=theta_min,
        eta_mb=eta_mb,
        telescope_diameter=telescope_diameter
        )

    eta_pol = 0.5
    eta_sw = eta_pol * eta_atm * eta_a * eta_forward

    spectral_NEFD_ = spectral_NEFD(
            NEPinst,
            eta_source_window=eta_sw,
            F=F,
            R=R,
            telescope_diameter=10.
        )

    if on_off == True:
        spectral_NEFD_ = np.sqrt(2) * spectral_NEFD_

    continuum_NEFD = spectral_NEFD_ * eta_IBF

    NEF = spectral_NEFD_ * W_F_spec
    MDLF = NEF * snr / np.sqrt(obs_hours*on_source_fraction*60.*60.)

    Trx = NEPinst/k/np.sqrt(2*W_F_cont) - T_from_psd(F, psd_wo)  # assumes RJ!

    # Make Pandas DataFrame out of the result

    result = pd.concat([
        pd.Series(F, name='F'),
        pd.Series(pwv, name='PWV'),
        pd.Series(EL, name='EL'),
        pd.Series(eta_atm, name='eta_atm'),
        pd.Series(R, name='R'),
        pd.Series(W_F_spec, name='W_F_spec'),
        pd.Series(W_F_cont, name='W_F_cont'),
        pd.Series(theta_maj, name='theta_maj'),
        pd.Series(theta_min, name='theta_min'),
        pd.Series(eta_a, name='eta_a'),
        pd.Series(eta_mb, name='eta_mb'),
        pd.Series(eta_forward, name='eta_forward'),
        pd.Series(eta_sw, name='eta_sw'),
        pd.Series(eta_window, name='eta_window'),
        pd.Series(eta_inst, name='eta_inst'),
        pd.Series(eta_circuit, name='eta_circuit'),
        pd.Series(T_from_psd(F, psd_sky), name='Tb_sky'),
        pd.Series(T_from_psd(F, psd_M1), name='Tb_M1'),
        pd.Series(T_from_psd(F, psd_M2), name='Tb_M2'),
        pd.Series(T_from_psd(F, psd_wo), name='Tb_wo'),
        pd.Series(T_from_psd(F, psd_window), name='Tb_window'),
        pd.Series(T_from_psd(F, psd_co), name='Tb_co'),
        pd.Series(T_from_psd(F, psd_KID), name='Tb_KID'),
        pd.Series(Pkid, name='Pkid'),
        pd.Series(Pkid_sky, name='Pkid_sky'),
        pd.Series(Pkid_warm, name='Pkid_warm'),
        pd.Series(Pkid_cold, name='Pkid_cold'),
        pd.Series(Pkid/(W_F_cont * h * F), name='n_ph'),
        pd.Series(NEPkid, name='NEPkid'),
        pd.Series(NEPinst, name='NEPinst'),
        pd.Series(spectral_NEFD_, name='NEFD_line'),
        pd.Series(continuum_NEFD, name='NEFD_continuum'),
        pd.Series(NEF, name='NEF'),
        pd.Series(MDLF, name='MDLF'),
        pd.Series(snr, name='snr'),
        pd.Series(obs_hours, name='obs_hours'),
        pd.Series(on_source_fraction, name='on_source_fraction'),
        pd.Series(obs_hours*on_source_fraction, name='on_source_hours'),
        pd.Series(Trx, name='equivalent_Trx'),
        ], axis=1
        )

    # Turn Scalar values into vectors
    result = result.fillna(method='ffill')

    return result


def eta_atm_func(F, pwv, EL=60., R=0):
    """
    Calculate eta_atm as a function of F by interpolation.
    If R~=0 then the function will average the atmospheric transmission
    within each spectrometer channel.

    Parameters
    ----------
    F : scalar or vector
        Frequency of the astronomical signal.
        Unit: Hz (works also for GHz, will detect)
    pwv : float
        precipitable water vapour.
        Unit: mm
    EL : float
        telescope elevation angle
        Unit: degrees
    R : float
        spectral resolving power in F/W_F
            W_F is the 'equivalent bandwidth'
                http://www.astrosurf.com/buil/us/spe2/hresol7.htm
        R is used to average the atmospheric trannsmission within
        one spectrometer channel.
        If R = 0, then the function will return the transmission at that
        exact frequency.
        Unit : None.

    Returns
    -------
    eta_atm : float (if F is scalar) or a 1D np.array (if F is a vector)
        atmospheric tranmsmission.
        Units: None.
    """
    if np.average(F) > 10.**9:
        F = F / 10.**9
    if not hasattr(F, "__len__"):  # give F a length if it is an integer.
        F = np.asarray([F])

    eta_atm_df = pd.read_csv(
        # os.path https://qiita.com/ymdymd/items/d758110d429f72bc10fb
        os.path.dirname(__file__)+'/data/atm.csv',
        skiprows=4,
        delim_whitespace=True,
        header=0
        )
    eta_atm_func_zenith = eta_atm_interp(eta_atm_df)

    if R == 0:
        eta_atm = np.abs(
                eta_atm_func_zenith(pwv, F)) ** (1./np.sin(EL*np.pi/180.))
    else:  # smooth with spectrometer resolution
        # 100.0, 100.1., ....., 1000 GHz as in the original data.
        F_highres = eta_atm_df['F']
        eta_atm_zenith_highres = eta_atm_func_zenith(pwv, F_highres)
        eta_atm = np.zeros(len(F))
        for i_ch in range(len(F)):
            eta_atm[i_ch] = np.mean(
                eta_atm_zenith_highres[(F_highres > F[i_ch]*(1-0.5/R)) &
                                       (F_highres < F[i_ch]*(1+0.5/R))])
        eta_atm = [eta_atm]

    if len(eta_atm) == 1:
        eta_atm = eta_atm[0]
    else:
        eta_atm = eta_atm[:, 0]

    return eta_atm


def eta_atm_interp(eta_atm_dataframe):
    """
    Used in the function eta_atm_func().
    Returns a function that interpolates atmospheric transmission data
    downloaded from ALMA
    (https://almascience.eso.org/about-alma/atmosphere-model)
    The returned function has the form of
    eta = func(F [GHz], pwv [mm]). Note telescope EL = 90 (zenith)

    Parameters
    ----------
    eta_atm_dataframe : pandas.DataFrame

    Returns
    --------
    func : function that returns the atmospheric transmission

    Example
    --------
        % read csv file with pandas (in e.g., Jupyter)
        eta_atm_df = pd.read_csv("<desim-folder>/data/atm.csv",skiprows=4,
                                 delim_whitespace=True,header=0)
        % make function from pandas file
        etafun = desim.eta_atm_interp(eta_atm_df)

    """
    x = np.array(list(eta_atm_dataframe)[1:]).astype(np.float)
    y = eta_atm_dataframe['F'].values
    z = eta_atm_dataframe.iloc[:, 1:].values
    func = interp2d(x, y, z, kind='cubic')
    return func


def rad_trans(T_bkg, T_mdm, eta):
    """
    Calculates radiation transfer through a semi-transparent medium.
    One can also use the same function for
    Johnson-Nyquist PSD (power spectral density) instead of temperature.

    Parameters
    ----------
    T_bkg : scalar or vector
        brightness temperature (or PSD) of the input
        Units: K
    T_mdm : scalar
        brightness temperature (or PSD) of the lossy medium
        Units: K
    eta : scalar or vector
        transmission of the lossy medium
        Units: K

    Returns
    -------
    T_b : brightness temperature (or PSD) of the output

    """
    T_b = eta * T_bkg + (1 - eta) * T_mdm
    return T_b


def window_trans(
        F,
        psd_in,
        psd_cabin,
        psd_co,
        thickness=8.e-3,    # in m
        tandelta=4.805e-4,  # tan delta, measured Biorad
        tan2delta=1.e-8,
        neffHDPE=1.52,
        ):
    """
    Calculates the window transmission.

    Parameters
    ----------
    F : scalar or vector.
        Frequency
        Units: Hz
    psd_in : scalar or vector.
        PSD of the incoming signal.
        Units : W / Hz
    psd_cabin : scalar or vector.
        Johnson-Nyquist PSD of telescope cabin temperature.
        Units : W / Hz
    psd_co : scalar or vector.
        Johnson-Nyquist PSD of cold-optics temperature.
        Units : W / Hz
    thickness: scalar or vector.
        thickness of the HDPE window.
        Units: m
    tandelta, tan2delta : scalar
        values from Stephen.
            "# 2.893e-8 %% tan delta, measured Biorat. I use 1e-8 as this fits
            the tail of the data better"
    neffHDPE : scalar
        refractive index of HDPE. set to 1 to remove reflections.
        Units : None.

    Returns
    -------
    psd_after_2nd_refl : scalar or vector
        PSD looking into the window from the cold optics
    eta_window : scalar or vector
        transmission of the window

    """
    # Parameters to calcualte the window (HDPE), data from Stephen
    # reflection. ((1-neffHDPE)/(1+neffHDPE))^2. Set to 0 for Ar coated.
    HDPErefl = ((1-neffHDPE)/(1+neffHDPE))**2
    eta_HDPE = np.exp(-thickness * 2 * np.pi * neffHDPE *
                      (tandelta * F / c + tan2delta * (F / c)**2))
    # most of the reflected power sees the cold.
    psd_after_1st_refl = rad_trans(psd_in, psd_co, 1.-HDPErefl)
    psd_before_2nd_refl = rad_trans(psd_after_1st_refl, psd_cabin, eta_HDPE)
    # the reflected power sees the cold.
    psd_after_2nd_refl = rad_trans(psd_before_2nd_refl, psd_co, 1.-HDPErefl)

    eta_window = (1.-HDPErefl)**2 * eta_HDPE

    return psd_after_2nd_refl, eta_window, HDPErefl


def nph(F, T):
    """
    Photon occupation number of Bose-Einstein Statistics.
    If it is not single temperature, use nph = Pkid/(W_F * h * F)

    Parameters
    ----------
    F : scalar or vector.
        Frequency
        Units: Hz
    T : scalar or vector.
        temperature
        Units: K

    Returns
    --------
    n : scalar or vector
        photon occupation number
        Units : None.
    """
    n = 1./(np.exp(h*F/(k*T))-1.)
    return n


def johnson_nyquist_psd(F, T):
    """
    Johnson-Nyquist power spectral density.
    Don't forget to multiply with bandwidth to caculate the total power in W.

    Parameters
    ----------
    F : scalar or vector.
        Frequency
        Units: Hz
    T : scalar or vector.
        temperature
        Units: K

    Returns
    --------
    psd : scalar or vector
        Power Spectral Density.
        Units : W / Hz
    """
    psd = h*F*nph(F, T)
    return psd


def T_from_psd(
        F,
        psd,
        method='Callen-Welton'
        ):
    """
    Calculate Callen-Welton temperature from the PSD a single frequency,
    or an array of frequencies.

    Parameters
    ----------
    F : scalar or vector.
        Frequency
        Units: Hz
    psd : scalar or vector
        Power Spectral Density.
        Units : W / Hz
    method: optional, sring.
        default: 'Callen-Welton'
        option: 'Rayleigh-Jeans'

    Returns
    --------
    T : scalar or vector.
        Callen-Welton temperature.
        Units : K

    """
    if method == 'Callen-Welton':
        T = h*F/(k*np.log(h*F/psd+1.))
    elif method is 'Rayleigh-Jeans':
        T = psd / k
    else:
        sys.exit("Error: Method should be Callen-Welton or Rayleigh-Jeans.")

    return T


def aperture_efficiency(
        F,
        theta_maj,
        theta_min,
        eta_mb,
        telescope_diameter,
        ):
    """
    Calculates telescope aperture efficiency.

    Parameters
    ----------
    F : scalar or vector.
        Frequency
        Units: Hz
    theta_maj : scalar or vector.
        The HPBW along the major axis, assuming a Gaussian beam.
        Unit: radians.
    theta_min : scalar or vector.
        The HPBW along the minor axis, assuming a Gaussian beam.
        Unit: radians.
    eta_mb : scalar or vector
        main beam efficiency.
        Unit: None.
    telescope_diameter : float or vector.
        diameter of the telescope.
        Units: m

    Returns
    -------
    eta_a: scalar or vector.
        aperture efficiency
        Units: None.

    """

    omega_mb = np.pi * theta_maj * theta_min / np.log(2) / 4
    omega_a = omega_mb / eta_mb
    lmd = c/F
    Ae = lmd**2 / omega_a
    Ag = np.pi * (telescope_diameter/2.)**2
    eta_a = Ae/Ag
    return eta_a


def eta_source_window(
        eta_a=0.171,
        eta_pol=0.5,
        eta_atm=0.9,
        eta_forward=0.94
        ):
    """
    Optical efficiency from an astronomical point source
    to the cryostat window.
    Factor 2 loss in polarization is included here.

    Parameters
    ----------
    eta_a : scalar or vector
        aperture efficiency
        Units: None.
    eta_pol : polarization efficiency. 0.5 for a 1-polarization system.
    eta_atm : scalar or vector.
        atmospheric trnasmission.
        Units: None.
    eta_forward : scalar or vector.
        Forward efficiency.
        Fraction of power seen by the instrument that points
        to the sky with respect to the warm environment.
        https://deshima.kibe.la/notes/324
        Units : None.

    Returns
    -------
    eta_source_window_ : scalar or vector.
        Optical efficiency from an astronomical point source
        to the cryostat window.
        Units : None.
    """
    eta_source_window_ = eta_pol * eta_atm * eta_a * eta_forward
    return eta_source_window_

def photon_NEP_kid(
        F,
        Pkid,
        W_F
        ):
    """
    NEP of the KID, with respect to the absorbed power.

    Parameters
    -----------
    F:  Frequency of the signal responsible for loading.
        Unit: Hz
    Pkid: Power absorbed by the KID.
        Unit: W
    W_F: detection bandwidth, with respect to the power that sets the loading.
        Unit: Hz
    
    Note
    --------
    Pkid/(W_F * h * F) gives the occupation number.
    """
    # photon_term = 2 * Pkid * (h*F + Pkid/W_F)
    poisson_term = 2 * Pkid * h * F
    bunching_term = 2 * Pkid * Pkid / W_F
    r_term = 4 * Delta_Al * Pkid / eta_pb
    NEPkid = np.sqrt(poisson_term + bunching_term + r_term)
    return NEPkid


def spectral_NEFD(
        NEPinst,
        eta_source_window,
        F=350.*10.**9.,
        R=500,
        telescope_diameter=10.,
        ):
    """
    Noise Equivalent Flux Density.

    Parameters
    ----------
    NEPinst : scalar or vector.
        NEPinst : Instrumnet NEP (https://arxiv.org/abs/1901.06934).
        Units: W Hz^0.5
    eta_source_window_ : scalar or vector.
        Optical efficiency from an astronomical point source
        to the cryostat window.
        Units : None.
    F : scalar or vector.
        Frequency
        Units : Hz
    R : scalar or vector.
        spectral resolving power in F/W_F
        W_F is the 'equivalent bandwidth'
            http://www.astrosurf.com/buil/us/spe2/hresol7.htm
        Unit : None.
    telescope_diameter : float or vector.
        diameter of the telescope.
        Units: m
    """
    NESP = NEPinst / eta_source_window  # noise equivalent source power
    radius = telescope_diameter / 2.
    Ag = np.pi * radius**2.  # physical diameter of the telescope
    # noise equivalent flux;
    # sqrt(2) is because NEP is defined for 0.5 s integration.
    NEF = NESP / Ag / np.sqrt(2)
    W_F_spec = F/R
    NEFD_ = NEF / W_F_spec
    return NEFD_
