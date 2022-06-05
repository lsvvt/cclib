"""
This file is an implementation of the Charge Model 5 that can be used to calculate CM5 Charges, dipole moment and quadrupole moment

It is based on this Fortran implementation: https://github.com/hokru/cm5charges
-----------------------------------------------
Points to be noted:
-----------------------------------------------
1) Only ORCA output files are supported, and "Print[P_Hirshfeld] 1" must be entered in the ORCA input file to produce Hirshfeld charges.
2) Single bond atomic radii are considered.
3) For Carbon, only sp3 atomic radius is considered.

-----------------------------------------------
Example on how to Use this class:
-----------------------------------------------
from cclib.method import CM5
from cclib.parser import ORCA

parser = ORCA("water_hpa.out") #test file found in /cclib/data/ORCA/basicORCA4.2/
data = parser.parse()

cm5 = CM5(data, 1.20)
print(cm5.cm5_charges())
print(cm5.dipole_moment())
print(cm5.quadrupole_moment())

------------------------------------------------
Output:
------------------------------------------------
[-0.3880329  0.2227029  0.16703  ]
(array([-3.7422439 , -3.34907393,  0.80222668]), 5.0856910330516865)
[[ 2.9476879   0.39972848 -0.47709812]
 [ 2.648237   -0.2199436  -0.65167883]
 [ 1.183168    1.256816   -0.11061444]]
"""

import logging

import numpy as np
import periodictable.covalent_radius as pt

from cclib.method.calculationmethod import Method


class CM5(Method):
    """Compute Charge Model 5 (CM5) atomic charges.

    The description of charges is from https://doi.org/10.1021/ct200866d."""
    def __init__(self, data, fscale=1.20, progress=None, loglevel=logging.INFO, logname="Log"):
        super().__init__(data, progress, loglevel, logname)

        self.required_attrs = ("natom", "atomcoords", "atomnos")
        self.fscale = fscale
        self.atomradius = np.empty(119)
        self.atomradius[0] = 0.20

        for line in pt.CorderoPyykko.split("\n"):
            fields = line.split()
            if line[0] == "#":
                continue
            else:
                fields = line.split()
                Z = int(fields[0])

                if len(fields) < 6:
                    for _ in range(len(fields), 6):
                        fields.append("0.0")

                if fields[2] == "-":
                    rC = 0.0
                    drC = 0.0
                else:
                    sfields = fields[2].split("(")
                    rC = float(sfields[0])
                    drC = float(sfields[1].split(")", 1)[0]) / 100 if len(sfields) == 2 else 0.0

                r1 = float(fields[3])
                r1_avg = (rC + r1) / 2 if r1 is not 0.0 else rC
                r2 = float(fields[4])
                r3 = float(fields[5])

            self.atomradius[Z] = r1_avg

    def cm5_charges(self):
        """Compute the CM5 atomic charges."""
        nat = self.data.natom
        qcm5 = np.empty(nat)
        z = self.data.atomnos
        xyz = self.data.atomcoords[-1]
        hirshfeld_charges = self.data.atomcharges["hirshfeld"]

        alpha = 2.474  # Angstrom

        for i in range(0, nat - 1):
            s = 0
            for j in range(0, nat - 1):
                if i != j:
                    rij = np.linalg.norm(np.subtract(xyz[i], xyz[j]))  # = nuclear.get_distances()
                    bij = np.exp(
                        -alpha * (rij - self.atomradius[z[i]] - self.atomradius[z[j]])
                    )  # eq.2
                    s += tij(z[i], z[j]) * bij
            qcm5[i] = hirshfeld_charges[i] + s
        return qcm5

    def dipole_moment(self):
        """Compute the dipole moment from CM5 atomic charges."""
        nat = self.data.natom
        dipole = np.empty(nat)
        cm5_charges = self.cm5_charges()
        for i in range(0, nat):
            for j in range(0, 2):
                dipole[j] += cm5_charges[i] * self.data.atomcoords[-1, j, i] * self.fscale
        dipole *= 4.802889778
        s = np.sqrt(dipole[0] ** 2 + dipole[1] ** 2 + dipole[2] ** 2)
        return dipole, s

    def quadrupole_moment(self):
        """Compute the quadrupole moment from CM5 atomic charges."""
        # This is the conversion factor used in https://github.com/hokru/cm5charges.
        # bohr = 0.52917726
        atomcoords = convertor(self.data.atomcoords, "Angstrom", "bohr")
        nat = self.data.natom
        quad = np.empty([nat, nat])
        cm5_charges = self.cm5_charges()
        for k in range(0, nat - 1):
            dx = atomcoords[-1, k, 0]
            dy = atomcoords[-1, k, 1]
            dz = atomcoords[-1, k, 2]
            quad[0, 0] += dx * dx * cm5_charges[k]
            quad[1, 1] += dy * dy * cm5_charges[k]
            quad[2, 2] += dz * dz * cm5_charges[k]
            quad[0, 1] += dx * dy * cm5_charges[k]
            quad[0, 2] += dx * dz * cm5_charges[k]
            quad[1, 2] += dy * dz * cm5_charges[k]
        return quad


def tij(i, j):
    """Compute eq. 4 from 10.1021/ct200866d.

    These include the extended set of parameters presented in the Supporting
    Information.
    """

    #               H-C     H-N     H-O     C-N     C-O     N-O
    dzz = np.array([0.0502, 0.1747, 0.1671, 0.0556, 0.0234, -0.0346])

    # catch special cases
    if i == 1:
        if j == 6:
            tij = dzz[1]
        elif j == 7:
            tij = dzz[2]
        elif j == 8:
            tij = dzz[3]
    elif i == 6:
        if j == 7:
            tij = dzz[4]
        elif j == 8:
            tij = dzz[5]
        elif j == 1:
            tij = -dzz[1]
    elif i == 7:
        if j == 8:
            tij = dzz[6]
        elif j == 1:
            tij = -dzz[2]
        elif j == 6:
            tij = -dzz[4]
    elif i == 8:
        if j == 1:
            tij = -dzz[3]
        elif j == 6:
            tij = -dzz[5]
        elif j == 7:
            tij = -dzz[6]
    else:
        dz = np.zeros((119,))
        dz[1] = 0.0056
        dz[2] = -0.1543
        dz[4] = 0.0333
        dz[5] = -0.1030
        dz[6] = -0.0446
        dz[7] = -0.1072
        dz[8] = -0.0802
        dz[9] = -0.0629
        dz[10] = -0.1088
        dz[11] = 0.0184
        dz[13] = -0.0726
        dz[14] = -0.0790
        dz[15] = -0.0756
        dz[16] = -0.0565
        dz[17] = -0.0444
        dz[18] = -0.0767
        dz[19] = 0.0130
        dz[31] = -0.0512
        dz[32] = -0.0557
        dz[33] = -0.0533
        dz[34] = -0.0399
        dz[35] = -0.0313
        dz[36] = -0.0541
        dz[37] = 0.0092
        dz[49] = -0.0361
        dz[50] = -0.0393
        dz[51] = -0.0376
        dz[52] = -0.0281
        dz[53] = -0.0220
        dz[54] = -0.0381
        dz[55] = 0.0065
        dz[81] = -0.0255
        dz[82] = -0.0277
        dz[83] = -0.0265
        dz[84] = -0.0198
        dz[85] = -0.0155
        dz[86] = -0.0269
        dz[87] = 0.0046
        dz[113] = -0.0179
        dz[114] = -0.0195
        dz[115] = -0.0187
        dz[116] = -0.0140
        dz[117] = -0.0110
        dz[118] = -0.0189

        tij = dz[i] - dz[j]

    return tij
