#!/usr/bin/env python
# -*- coding: utf-8 -*-
# YAFF is yet another force-field code
# Copyright (C) 2011 - 2013 Toon Verstraelen <Toon.Verstraelen@UGent.be>,
# Louis Vanduyfhuys <Louis.Vanduyfhuys@UGent.be>, Center for Molecular Modeling
# (CMM), Ghent University, Ghent, Belgium; all rights reserved unless otherwise
# stated.
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
#--


import sys, argparse, traceback, numpy as np
from fnmatch import fnmatch
from yaff import *


#log.set_level(log.high)


def parse_args():
    parser = argparse.ArgumentParser(prog='opttest.py',
        description='Test driver for the geometry/cell optimizer in YAFF.')
    parser.add_argument('test', default=None, nargs='?',
        help='Select one test to run. If not given, all tests are executed.')
    parser.add_argument('-v', '--verbose', default=False, action='store_true',
        help='Do not suppress the output during the optimization.')
    parser.add_argument('-x', '--xyz', default=False, action='store_true',
        help='Write XYZ trajectory files for the optimizations.')
    return parser.parse_args()


class FileFormatError(IOError):
    pass


fields = {
    'case': (True, str),
    'system': (True, str),
    'forcefield': (True, str),
    'maxiter': (True, int),
    'energy': (True, (lambda s: float(s)*kjmol)),
    'dof': (True, {'cartesian': CartesianDOF, 'strain': StrainCellDOF}),
    'gpos_rms': (False, float),
    'neg_hessian_evals': (False, int),
}


def load_cases(fn, select_title=None):
    # 1) Load the file
    log('Loading test cases from %s' % fn)
    cases_data = {}
    with open(fn) as f:
        for line in f:
            # Read line, skip comments and empty lines
            line = line[:line.find('#')].strip()
            if len(line) == 0:
                continue
            # Split line into key and data
            words = line.split()
            if len(words) != 2:
                raise FileFormatError('A line should contain exactly two words.')
            key, data = words
            # Store line
            if key not in fields:
                raise FileFormatError('Uknown key encountered: %s' % key)
            if key == 'case':
                current = {}
                cases_data[data] = current
            elif current is None:
                raise FileFormatError('The first line should have a \'case\' key.')
            current[key] = data

    # 2) Convert the arguments:
    for args in cases_data.itervalues():
        title = args['case']
        for name, (required, fieldtype) in fields.iteritems():
            if name not in args:
                if required:
                    raise FileFormatError('Case \'%s\' does not have a field \'%s\'.' % (title, name))
                else:
                    continue
            if isinstance(fieldtype, type) or callable(fieldtype):
                try:
                    args[name] = fieldtype(args[name])
                except TypeError:
                    raise FileFormatError('The field \'%s\' of case \'%s\' could not be converted to the type %s' % (name, title, type))
            elif isinstance(fieldtype, dict):
                data = args[name]
                if data not in fieldtype:
                    raise FileFormatError('Could not interpert field \'%s\' of case \'%s\'. Please select one of %s' % (name, title, fieldtype.keys()))
                args[name] = fieldtype[data]
            else:
                raise NotImplementedError

    if select_title is not None:
        cases_data = dict((name, args) for name, args in cases_data.iteritems() if fnmatch(name, select_title))
        if len(cases_data) == 0:
            raise ValueError('Could not find test case \'%s\'.' % select_title)

    # 3) Make Case objects
    cases = []
    for args in cases_data.itervalues():
        title = args['case']
        log('Preparing case \'%s\'.' % title)
        system = System.from_file(context.get_fn(args['system']))
        if system.cell.nvec == 0:
            ff_args = {'rcut': 200.0}
        else:
            ff_args = {}
        ff = ForceField.generate(system, context.get_fn(args['forcefield']), **ff_args)
        dof_args = dict((key, data) for key, data in args.iteritems() if (key.endswith('_rms') or key.endswith('_max')))
        dof = args['dof'](ff, **dof_args)
        maxiter = args['maxiter']
        energy = args['energy']
        neg_hessian_evals = args.get('neg_hessian_evals', None)
        case = Case(title, ff, dof, maxiter, energy, neg_hessian_evals)
        cases.append(case)

    return cases


class Case(object):
    def __init__(self, title, ff, dof, maxiter, energy, neg_hessian_evals):
        self.title = title
        self.ff = ff
        self.dof = dof
        self.maxiter = maxiter
        self.energy = energy
        self.neg_hessian_evals = neg_hessian_evals

    def run(self, verbose, xyz):
        if not verbose:
            output = open('/dev/null', 'w')
            log.set_file(output)

        self._optimize(verbose, xyz)
        if self.neg_hessian_evals is not None:
            self._check_hessian()

        if not verbose:
            log.set_file(sys.stdout)
            output.close()

        self._report()

    def _optimize(self, verbose, xyz):
        self.ff.system.pos *= np.random.uniform(0.99, 1.01, self.ff.system.pos.shape)
        try:
            hooks = []
            if xyz:
                hooks.append(XYZWriter('trajectory_%s.xyz' % self.title))
            opt = QNOptimizer(self.dof, hooks=hooks)
            opt.run(self.maxiter)
            self.error = False
        except:
            traceback.print_exc()
            self.error = True
            pass
        self.energy = self.ff.energy
        self.gpos = self.ff.gpos
        self.niter = opt.counter

    def _check_hessian(self):
        if self.ff.system.cell.nvec != 0:
            # external rotations should be implemented properly for periodic systems.
            # 1D -> one external rotation, 2D and 3D -> no external rotation
            raise NotImplementedError('The hessian test is only working for isolated systems')
        # compute hessian
        hessian = estimate_cart_hessian(self.ff)
        # construct basis of external/internal degrees (rows)
        x, y, z = self.ff.system.pos.T
        natom = self.ff.system.natom
        ext_basis = np.array([
            [1.0, 0.0, 0.0]*natom,
            [0.0, 1.0, 0.0]*natom,
            [0.0, 0.0, 1.0]*natom,
            # TODO: this assumes geometry is centered for good conditioning
            np.ravel(np.array([np.zeros(natom), z, -y]).T),
            np.ravel(np.array([-z, np.zeros(natom), x]).T),
            np.ravel(np.array([y, -x, np.zeros(natom)]).T),
        ]).T
        u, s, vt = np.linalg.svd(ext_basis, full_matrices=True)
        rank = (s > s.max()*1e-10).sum() # for linear and
        int_basis = u[:,rank:]
        # project hessian
        int_hessian = np.dot(int_basis.T, np.dot(hessian, int_basis))
        evals = np.linalg.eigvalsh(int_hessian)
        self.num_neg_evals = (evals < 0).sum()
        # call tamkin as double check
        import tamkin
        system = self.ff.system
        mol = tamkin.Molecule(system.numbers, system.pos, system.masses, self.energy, self.gpos, hessian)
        nma = tamkin.NMA(mol, tamkin.ConstrainExt())
        invcm = lightspeed/centimeter
        #print nma.freqs/invcm
        self.num_neg_evals = (nma.freqs < 0).sum()


    def _report(self):
        if self.error:
            self.status = 'ERROR'
        elif not self.dof.converged:
            self.status = 'FAILED'
        elif self.ff.energy > self.energy:
            self.status = 'HIGH-ENERGY'
        elif self.neg_hessian_evals is not None and self.num_neg_evals != self.neg_hessian_evals:
            self.status = 'HESSIAN'
        else:
            self.status = 'SUCCESS'
        log('%s %11s %5i %10s %3s' % (
            self.title.ljust(39),
            self.status, self.niter,
            log.energy(self.energy),
            '   ' if self.neg_hessian_evals is None else str(self.num_neg_evals),
        ))


def main():
    args = parse_args()
    with log.section('LOAD'):
        cases = load_cases(context.get_fn('opttest/cases.txt'), args.test)
    with log.section('RUN'):
        log('Case                                         Status #iter     Energy Neg')
        log.hline()
        niters = []
        status_counts = {}
        success = True
        for case in cases:
            case.run(args.verbose, args.xyz)
            niters.append(case.niter)
            status_counts[case.status] = status_counts.get(case.status, 0) + 1
            success &= case.status == 'SUCCESS'
        log.hline()
        log('Total number of iterations:   %i' % sum(niters))
        log('Maximum number of iterations: %i' % max(niters))
        log('Number of tests:              %i' % len(cases))
        if success:
            log('OK')
        else:
            log('Failure: %s' % ', '.join('%i %s' % (count, status) for status, count in sorted(status_counts.iteritems())))
            sys.exit(-1)


if __name__ == '__main__':
    main()
