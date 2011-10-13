# YAFF is yet another force-field code
# Copyright (C) 2008 - 2011 Toon Verstraelen <Toon.Verstraelen@UGent.be>, Center
# for Molecular Modeling (CMM), Ghent University, Ghent, Belgium; all rights
# reserved unless otherwise stated.
#
# This file is part of YAFF.
#
# YAFF is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 3
# of the License, or (at your option) any later version.
#
# YAFF is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, see <http://www.gnu.org/licenses/>
#
# --


import h5py

from yaff import *
from yaff.sampling.test.common import get_ff_water32

def test_basic():
    nve = NVEIntegrator(get_ff_water32(), 1.0*femtosecond)
    nve.run(5)
    assert nve.counter == 5


def check_hdf5_common(f):
    assert 'system' in f
    assert 'numbers' in f['system']
    assert 'ffatypes' in f['system']
    assert 'ffatype_ids' in f['system']
    assert 'pos' in f['system']
    assert 'bonds' in f['system']
    assert 'rvecs' in f['system']
    assert 'charges' in f['system']
    assert 'trajectory' in f
    assert 'counter' in f['trajectory']
    assert 'time' in f['trajectory']
    assert 'epot' in f['trajectory']
    assert 'pos' in f['trajectory']
    assert 'vel' in f['trajectory']
    assert 'rmsd_delta' in f['trajectory']
    assert 'rmsd_gpos' in f['trajectory']
    assert 'ekin' in f['trajectory']
    assert 'temp' in f['trajectory']
    assert 'etot' in f['trajectory']
    assert 'econs' in f['trajectory']


def test_hdf5():
    f = h5py.File('tmp.h5', driver='core', backing_store=False)
    hdf5 = HDF5Writer(f)
    nve = NVEIntegrator(get_ff_water32(), 1.0*femtosecond, hooks=hdf5)
    nve.run(15)
    assert nve.counter == 15
    check_hdf5_common(hdf5.f)
    assert hdf5.f['trajectory'].attrs['row'] == 16
    assert hdf5.f['trajectory/counter'][15] == 15


def test_hdf5_start():
    f = h5py.File('tmp.h5', driver='core', backing_store=False)
    hdf5 = HDF5Writer(f, start=2)
    nve = NVEIntegrator(get_ff_water32(), 1.0*femtosecond, hooks=hdf5)
    nve.run(5)
    assert nve.counter == 5
    check_hdf5_common(hdf5.f)
    assert hdf5.f['trajectory'].attrs['row'] == 4
    assert hdf5.f['trajectory/counter'][3] == 5


def test_hdf5_step():
    f = h5py.File('tmp.h5', driver='core', backing_store=False)
    hdf5 = HDF5Writer(f, step=2)
    nve = NVEIntegrator(get_ff_water32(), 1.0*femtosecond, hooks=hdf5)
    nve.run(5)
    assert nve.counter == 5
    check_hdf5_common(hdf5.f)
    assert hdf5.f['trajectory'].attrs['row'] == 3
    assert hdf5.f['trajectory/counter'][2] == 4


def test_xyz():
    xyz = XYZWriter('/dev/null')
    nve = NVEIntegrator(get_ff_water32(), 1.0*femtosecond, hooks=[xyz])
    nve.run(15)
    assert nve.counter == 15


def test_at():
    nve = NVEIntegrator(get_ff_water32(), 1.0*femtosecond, hooks=AndersenThermostat(300))
    nve.run(5)
    assert nve.counter == 5


def test_at_mask():
    nve = NVEIntegrator(get_ff_water32(), 1.0*femtosecond, hooks=AndersenThermostat(300, mask=[1,2,5]))
    nve.run(5)
    assert nve.counter == 5


def test_at_annealing():
    nve = NVEIntegrator(get_ff_water32(), 1.0*femtosecond, hooks=AndersenThermostat(300, annealing=0.9))
    nve.run(5)
    assert nve.counter == 5


def test_kinetic_annealing():
    nve = NVEIntegrator(get_ff_water32(), 1.0*femtosecond, hooks=KineticAnnealing())
    nve.run(5)
    assert nve.counter == 5
