#!/usr/bin/python
#    Ported to Python and barely optimized by Hernan Chavez Thielemann

__merged_files__ = ['main.m', 'Reading_top.m', 'Reading_bon.m',
                    'Reading_nb.m','Counting_lines.m', 'Reading_xyz.m']


from lib.misc.warn import wrg_1, wrg_3, pop_err_1, pop_wrg_1
from lib.misc.file import check_file, debugger_file
from sys import exit


def extract_gromacs_data( _data_files_, _water_names_, _ck_buttons_):
    
    ''' data files ---> ['gro file', 'top file', 'forcefield',
        'non bonded file', 'bonded file']'''
    
    filename_gro    =   _data_files_[0]
    filename_top    =   _data_files_[1]
    filename_ff     =   _data_files_[2]
    filename_nb     =   _data_files_[3]
    filename_bon    =   _data_files_[4]
    
    data_container  =   {}
    data_container['define'] = {}
    _solvated_f_, _autoload_= _ck_buttons_
    if not _autoload_:
        print filename_ff # or not
        
    data_container['defaults'], ok_flag = ck_forcefield( filename_ff)
    if not ok_flag:
        return {}, ok_flag
    
    buckorlj = int(data_container['defaults'][0])
    
    print 'Solvation: {} | Autoload: {}\n'.format( *_ck_buttons_)
    
    
    #################################################
    '''----------------  FILE GRO  ---------------'''
    #===============================================#
    
    ok_flag, gro_pack, b_xyzhi = get_gro_fixed_line( filename_gro)
    if not ok_flag:
        return {}, ok_flag
    
    _mol_, _mtype_, _type_, _xyz_, _mtypes_ = gro_pack
    data_container['atomsdata'] = [ _mol_, _mtypes_, _type_, _xyz_, _mtype_]
    
    
    #################    BOX DEF   ##################
    xlo = 0
    xhi = b_xyzhi[0]*10
    ylo = 0
    yhi = b_xyzhi[1]*10
    zlo = 0
    zhi = b_xyzhi[2]*10   
    data_container['box']=[xlo,xhi, ylo,yhi, zlo,zhi]
    
    
    #################################################
    '''----------------  FILE TOP  ---------------'''
    #===============================================#
    
    startstrings=['[ moleculetype ]', '[ atoms ]','[ bonds ]', '[ pairs ]',
                  '[ angles ]', '[ dihedrals ]', '[ system ]',
                  '[ molecules ]', '']
    
    for ti in range(len(startstrings))[:-1]:
        _char_str_ = startstrings[ti][ 2:-2]
        ''' here is possible to insert a selector in case pairs and 
        others can be ovbiated'''
        data_container[_char_str_] , ok_flag, _ = get_gro_line( filename_top,
                                                                startstrings,
                                                               ti)
        
        if not ok_flag:
            print wrg_3( 'Not ok flag in <extract_gromacs_data> top file' +
                         'section, in ' + _char_str_)
            return {}, ok_flag
        
        #debugger_file( _char_str_, data_container[_char_str_])
            
    n_atoms     =   len( data_container['atoms'])
    n_bonds     =   len( data_container['bonds'])
    n_angles    =   len( data_container['angles'])
    
    
    #################################################
    '''----------  SIDE MOLE FILES   -------------'''
    #===============================================#
    #### research in topology for new molecules / side molecules
    if _autoload_:
        data_container, ok_flag = sidemol_data( filename_top, data_container)
    if not ok_flag:
        return {}, ok_flag
    
    
    #################################################
    '''-----------------  FILE NB  ---------------'''
    #===============================================#
    startstrings = ['[ atomtypes ]', '[ nonbond_params ]']
    
    data_container['atomtypes'], ok_flag, _ = get_gro_line( filename_nb,
                                                         startstrings)
    if not ok_flag:
        return {}, ok_flag
    
    n_atomtypes     =   len( data_container['atomtypes'])
    
    #debugger_file( 'atomtypes',data_container['atomtypes'])
    #################################################
    '''----------------  FILE BON  ---------------'''
    #===============================================#
    
    
    startstrings=['[ bondtypes ]', '[ angletypes ]', '[ dihedraltypes ]', '']
    
    for bi in range(len(startstrings))[:-1]:
        _char_str_ = startstrings[bi][ 2:-2]
        
        _aux_here_ = get_gro_line( filename_bon, startstrings, bi)
        data_container[ _char_str_], ok_flag, _data_define_ = _aux_here_
        data_container['define'][_char_str_[:-5]] = _data_define_
        #debugger_file(_char_str_, data_container[_char_str_])
                
        if not ok_flag:
            return {}, ok_flag
        
    n_bondstypes    =   len( data_container['bondtypes'])
    n_anglestypes   =   len( data_container['angletypes'])
    
    
    #################################################
    '''----------------  Impropers ---------------'''
    #===============================================#
    # Search for impropers in TOP and BON, using crossreference if needed
    data_container = split_dihedral_improper( data_container)
    
    n_dihedrals     =   len( data_container['dihedrals'])
    n_dihedraltypes =   len( data_container['dihedraltypes'])
    n_impropers     =   len( data_container['impropers'])
    n_impropertypes =   len( data_container['impropertypes'])
    
    #################################################
    '''--------------  "Solvation"  --------------'''
    #===============================================#
    n_atomsnew = len( _type_)
    
    if _autoload_:
        # research in topology for new molecules / side molecules
        data_container, ok_flag = sidemol_data( filename_top, data_container)
        if not ok_flag:
            return {}, ok_flag
        
        # A_02 maths
        sidemol = data_container['sidemol']
        side_bonds_n = 0
        side_angles_n = 0
        for sb in range( len( sidemol['tag'])):
            bonds_x_mol = len( sidemol['data'][sb]['bonds'])
            angles_x_mol = len( sidemol['data'][sb]['angles'])
            
            side_bonds_n += sidemol['num'][sb]*bonds_x_mol
            side_angles_n += sidemol['num'][sb]*angles_x_mol
        
        n_bondsnew = n_bonds + side_bonds_n
        n_anglesnew = n_angles + side_angles_n
        
        print n_bonds, side_bonds_n, n_bonds + side_bonds_n
        print n_angles, side_angles_n, n_angles + side_angles_n
        
        # Regarding the itp format:
        #   charges index 6 in data-atoms
        #   opls names in index 1
        #   atom tags in index 4
        _charge_ = {}
        _conv_dict_ = {}
        for sb in range( len( sidemol['tag'])):
            for at in range( len( sidemol['data'][sb]['atoms'])):
                a_opls_tag = sidemol['data'][sb]['atoms'][at][1]
                a_elem_tag = sidemol['data'][sb]['atoms'][at][4]
                a_charge = float( sidemol['data'][sb]['atoms'][at][6])
                _charge_[a_opls_tag] = a_charge
                _conv_dict_[ a_elem_tag] = a_opls_tag
        print 'Charges found: '
        print _charge_
        print _conv_dict_
        
        data_container['S_charge'] =_charge_
        data_container['S_translation'] =_conv_dict_
        
    ##======= OLD TIMES :-)
    elif _solvated_f_:
        n_molwater=0
        _aux_m_ = data_container['molecules']
        for i in range(len(_aux_m_)) :
            if _aux_m_[i][0]=='SOL':
                n_molwater = int(_aux_m_[i][1])
                break
        
        n_bondsnew = n_bonds + 2*n_molwater
        n_anglesnew = n_angles + n_molwater
        
        _ch_H_ = float(_water_names_[4])
        _ch_O_= float(_water_names_[4])*-2
        _charge_ = {_water_names_[0]: _ch_O_, _water_names_[1]: _ch_H_}
        
        oxy_gf = _water_names_[2].split(',')
        hyd_gf = _water_names_[3].split(',')
        _conv_dict_ = {}
        for Ox in oxy_gf:
            _conv_dict_[Ox.strip(' ')] = _water_names_[0]
            #_charge_[Ox] = _ch_O_
        for Hy in hyd_gf:
            _conv_dict_[Hy.strip(' ')] = _water_names_[1]
            #_charge_[Hy] = _ch_H_
            
        data_container['S_charge'] =_charge_
        data_container['S_translation'] =_conv_dict_
        
    
    else:
        n_bondsnew = n_bonds
        n_anglesnew = n_angles
        indexoxy = 0
        indexhyd = 0
        #indexsod=0;
        n_atomsnew = n_atoms
        
    data_container['numbers']={}
    data_container['numbers']['total'] = [n_atomsnew, n_bondsnew,
                                          n_anglesnew, n_dihedrals, n_impropers
                                         ]
    data_container['numbers']['type'] = [n_atomtypes, n_bondstypes,
                                         n_anglestypes, n_dihedraltypes,
                                         n_impropertypes]
    

    return data_container, ok_flag

def sidemol_data( _file_top_, data_container):
    ''' getter of the side molecules data'''
    
    sidemol = {'tag': [],'num':[], 'data':[] }# Tag # mol_number
    sm_flag = True
    # names of non side molecules
    non_sm = data_container['moleculetype']
    non_sm = [non_sm[i][0] for i in range(len(non_sm))]
    # side molecules info
    _aux_m_ = data_container[ 'molecules']
    
    for i in range( len( _aux_m_)) :
        if _aux_m_[i][0] not in non_sm:
            sidemol['tag'].append( _aux_m_[i][0])
            sidemol['num'].append( int(_aux_m_[i][1]))
            
    #////////========= Side molecule >>> file <<< search   ============////////
    print ('Loading side molecule files: ' )
    _sm_files_ = []
    root_folder = '/'.join( _file_top_.split('/')[:-1]+[''])
    with open( _file_top_, 'r')  as topdata:
        _buffer_ = ''
        for k_line in topdata:
            if k_line.startswith('#'):
                logic_test = ('#if' not in _buffer_ and _buffer_ <> '')
                if k_line.startswith('#include') and logic_test:
                    new_filename = k_line.split('"')[1].lstrip('.').lstrip('/')
                    _sm_files_.append( root_folder + new_filename)
                    print _sm_files_[-1]
                    sm_flag *= check_file( _sm_files_[-1], content='[ atoms ]')
                else:
                    _buffer_ = k_line
    # do it in the same loop or not that is the thing... maybe is better
    # to not just beacause the indentation going to +inf atoms
    #////////========= Side molecule >>> data <<< search   ============////////
    if sm_flag:
        for sm in sidemol['tag']:
            aux_data, aux_flag = sidemol_data_gatherer( _sm_files_, sm)
            sm_flag *= aux_flag
            sidemol['data'].append( aux_data)
            
    
    data_container['sidemol'] = sidemol
    return data_container, sm_flag

def sidemol_data_gatherer( _sm_files_, sm):
    ''' collects all the data related with one kind of side molecule
        the data types are specified in startstrings
    '''
    _flag_ = True
    _file_ = ''
    _sm_data_c_ = {}
    # is sm in sm_file?? in cases with more than one file
    for smfile in _sm_files_:
        with open( smfile, 'r')  as sm_data:
            for j_line in sm_data:
                if j_line.startswith('[ moleculetype ]'):
                    j_line = sm_data.next()
                    j_line = sm_data.next()
                    if j_line.startswith(sm):
                        _file_ = smfile
                        break
    if _file_=='':
        pop_err_1('Error!! side molecule {} not found in itp -- '.format( sm))
        _flag_ = False
    else:
        tag_str = [ 'atoms', 'bonds', 'angles', 'dihedral','fin']
        _sm_data_c_ = { x:[] for x in tag_str if x <> 'fin'}
        read_flag = False
        iner_flag = False
        cd_tag = ''
        i=0
        with open( _file_, 'r')  as sm_data:
            for j_line in sm_data:
                if j_line.startswith(';') or j_line.startswith('#'):
                    pass
                # at this point starts reading
                elif j_line.startswith( sm):
                    read_flag = True
                elif len( j_line.rstrip()) < 2:
                    #print j_line
                    iner_flag = False
                elif read_flag and j_line.startswith('[ '):
                    content = j_line.lstrip('[ ').rstrip(' ]\n')
                    if content == tag_str[i]:
                        cd_tag = tag_str[i]
                        iner_flag = True
                        i+=1
                        
                    elif content == 'moleculetype':
                        break
                    else:
                        print '> {} not considered in {}'.format( content, sm)
                
                elif iner_flag:
                    # print j_line.rstrip()
                    _sm_data_c_[cd_tag].append( j_line.rstrip().split())
                    
        # todo add a new check in case of empty container
    return _sm_data_c_, _flag_

def split_dihedral_improper( _data_container_):
    ''' Seems that in GROMACS, impropers are present as a kind of 
        dihedral type, so this function is meant to pick the dihedral
        data and split it resizing the original container and creating
        a new improper-container.
        
        Creates #define data in dihedrals
        
        Also creates the data regarding kinds of functions. Useful when
        '1' and '3' are used in the same file
        
    '''
    
    DihedralKind = '1'
    ImproperKind = '2'
    RyckBellKind = '3'
    
    _dihedrals_data_ = _data_container_['dihedrals']
    #====================================================
    ''' ============  Dihedral TOP data   =========== ''' 
    im_data_ = []
    dh_data_ = []
    
    def_dihe_extra = [] # ---------------------------------CanBDel?
    def_impr_extra = []
    
    def_dihe_type_set = set()
    def_impr_type_set = set()
    dihe_kind_name = set() 
    for i in range( len ( _dihedrals_data_)):
        #  Dihedral line format in :
        #  ai  aj  ak  al  funct   c0  c1  c2  c3  c4  c5
        if _dihedrals_data_[i][4] in [ DihedralKind, RyckBellKind]:
            dh_data_.append( _dihedrals_data_[i])
            dihe_kind_name.add( _dihedrals_data_[i][4])
            
            if len (_dihedrals_data_[i])>5:
                def_dihe_extra.append( _dihedrals_data_[i])
                def_dihe_type_set.add( _dihedrals_data_[i][5:])
                
                
        elif _dihedrals_data_[i][4] == ImproperKind:
            im_data_.append( _dihedrals_data_[i])
            if len (_dihedrals_data_[i])>5:
                def_impr_extra.append( _dihedrals_data_[i])
                def_impr_type_set.add( _dihedrals_data_[i][5:])
        else:
            print 'Problem #008 here'
    
    # Save/overwriting point
    _data_container_['dihe_kinds'] = dihe_kind_name
    _data_container_['impropers'] = im_data_
    _data_container_['dihedrals'] = dh_data_
    #====================================================
    ''' ======== "Type" Dihedral BONDED data  ======= '''
    _dihe_type_data_ = _data_container_['dihedraltypes']
    im_type_ = []
    dh_type_ = []
    for i in range( len ( _dihe_type_data_)):
        #  Dihedral line format:
        #  ai  aj  ak  al  funct   c0  c1  c2  c3  c4  c5
        if _dihe_type_data_[i][4] == ImproperKind:
            im_type_.append( _dihe_type_data_[i])
        else:
            dh_type_.append( _dihe_type_data_[i])
    # Save/overwriting point
    _data_container_['impropertypes'] = im_type_
    _data_container_['dihedraltypes'] = dh_type_
    #====================================================
    ''' ========  Dihedral "#define" data  ========== ''' 
    def_dihe_dic = {}
    def_impr_dic = {}
    # If there are define potentials, I have to process... by types and kind
    '''    Make it homogeneous - New kind creations   '''
    # first_clause = ( maybe should be an inner clause
    '''     Now supposing that just #define exist with a tag in the c0
            position...'''
    new_dihedraltypes = set()
    define_dic = _data_container_['define']['dihedral']
    if define_dic <> {}:
        
        known_atoms = _data_container_['atoms']
        for dh in range( len( def_dihe_extra)):
            _dhi_ = def_dihe_extra[ dh]
            
            a_tag = ['',]*4
            for at1 in range( 4): # at1 0 1 2 3
                atnum = int( _dhi_[at1])
                if ( known_atoms[ atnum - 1][0] == _dhi_[ at1]):
                    a_tag[at1] = known_atoms[ atnum - 1][4]
                # Si no esta ordenado nos vamos casi a la...
                else:
                    # Brute force, til should be found
                    for at2 in range( len( known_atoms)):
                        if known_atoms[at2][0] == _dhi_[at1]:
                            a_tag[at1] = known_atoms[at2][4]
                            break
                            
                if '' == a_tag[at1]:
                    _string_ = 'Error!! atom number {} not found in .top -- '
                    pop_err_1( _string_.format( atnum))
            #### TODO Flag
            ## First case with coefs in the top file... c0  c1  c2  c3  c4  c5
            if len( _dhi_) > 6:
                print'Coefficients in the top file not supported yet'
                new_dihedraltypes.add(a_tag + _dhi_[4:])
            ## Second case with #define
            elif len( _dhi_) == ( 4 + 1 + 1):
                dh_kind_, dihedral_tag = _dhi_[4:]
                _coefs_ = define_dic[ dihedral_tag]
                new_dihedraltypes.add(a_tag + [dh_kind_] + _coefs_)
                
        for ndh in new_dihedraltypes:
                dh_type_.append( ndh)
        _data_container_['dihedraltypes'] = dh_type_
    
    
    return _data_container_

def get_gro_fixed_line(_filename_):
    ''' reading gromacs gro fixed lines'''
    _content_ = []
    _mol_=[]
    _mtype_=[]
    g_names =[]
    _type_=[]
    _xyz_=[]
    _corrupt = True
    with open(_filename_, 'r')  as indata:
        read_flag = False
        at=0
        at_num = 0
        
        _buffer = []
        for j_line in indata:
            if read_flag:
                at+=1
                mtype = j_line[5:10].strip(' ')
                
                _mol_.append( j_line[:5].lstrip(' '))
                _mtype_.append(mtype)
                _type_.append(j_line[10:15].lstrip(' '))
                _xyz_.append([j_line[20:28], j_line[28:36], j_line[36:44]])
                
                if _buffer==[]:
                    _buffer = [ mtype, at]
                ## TODO : Analyze if it is possible to improve here using sets
                elif mtype<>_buffer[0]:
                    
                    _buffer += [at-1]
                    g_names.append( _buffer)
                    _buffer = [ mtype, at]
                
                
                if at == at_num:
                    read_flag = False
                    g_names.append(_buffer+ [at])
                    
            elif j_line.startswith(';'):
                pass
            elif at_num==0:
                j_line = indata.next()
                at_num = int(j_line)
                read_flag = True
            elif at == at_num:
                _corrupt = False
                box_xyz_hi = [float(x) for x in j_line.split(';')[0].split()]
                
                
    if at_num<>len(_type_):
        pop_err_1('Atom number mismatch in .gro file')
        return False, 0 ,0
    elif _corrupt:
        pop_err_1('Corrupt .gro file')
        return False, 0,0
    else:
        return  True, [_mol_, _mtype_, _type_, _xyz_, g_names], box_xyz_hi

def top_groups(mtype, _buffer, g_names):
    
    return _buffer, g_names # hook

def get_gro_line( _filename_, _startstrings_, _i_=0):
    ''' reading gromacs content lines
        spliting by the space between info
    '''
    content_line = []
    _define_ = {}
    _ss_=_startstrings_
    # \* TODO: apply a method just in case that
    #          some _startstrings_ are not there ??
    with open(_filename_, 'r')  as indata:
        read_flag = False
        ok_flag = True
        tag_not_found = True
        #print _i_, _ss_[_i_], _ss_[_i_+1]
        for j_line in indata:
            # I just whant to read once the flag is on
            if read_flag:
                _line_ = j_line.split(';')[0].split()
                # getting out comments and empty lines
                if len( _line_)<1: 
                    pass
                    
                elif _line_[0][0] == '#':
                    if _line_[0] == '#include':
                        print wrg_3( _line_[1] + ' skipped this time')
                    elif _line_[0] == '#define':
                        _define_[_line_[1]] = _line_[2:]
                    else:
                        print wrg_3( str(_line_) + '  ??')
                        
                elif ' '.join(_line_)  == _ss_[_i_+1]:
                    #print 'exit here 424'
                    read_flag = False
                    
                elif len( _line_) > 1:
                    #if _i_==7:  print _line_
                    content_line.append( _line_)
                else:
                    print 'Ups... please raise an issue ;)'
            elif j_line.lstrip().startswith( _ss_[_i_]):
                #print _ss_[_i_]
                read_flag = True
                tag_not_found = False
    
    if content_line == [] or tag_not_found:
        if '/' in _filename_:
            _filename_ = _filename_.split('/')[-1]
        pop_err_1( 'The {} section is missing on {} file'.format( _ss_[_i_] ,
                                                                  _filename_)
                 )
        ok_flag = False
    return content_line, ok_flag, _define_

def get_ffldfiles( _topfile_):
    ''' 
    self explanatory... sub routine to get the force field files
    if they are stated in the top file.
    '''
    ff_file = ''
    
    with open( _topfile_, 'r')  as indata:
        for j_line in indata:
            if j_line.startswith('#include'):
                ff_file =  j_line.split('"')[1]
                break
            elif j_line.startswith('[ moleculetype ]'):
                break
    
    root_folder = '/'.join(_topfile_.split('/')[:-1]+[''])
    ff_file = ff_file.lstrip('.').lstrip('/')
    
    if ff_file <> '':
        file_cont = ['', '', '']
        print '----- Loading :'
        file_cont[0] =  root_folder + ff_file
        print file_cont[0]
        i = 0
        root_folder = '/'.join( file_cont[0].split('/')[:-1]+[''])
        with open( file_cont[0], 'r')  as indata2:
            for k_line in indata2:
                if k_line.startswith('#include'):
                    i+=1
                    file_cont[i] = ( root_folder + k_line.split('"')[1])
                    print file_cont[i]
                    if i==2:
                        break
    else:
        pop_wrg_1(' itp file not found')
        
    if '' in file_cont:
        return ['', '', '']
    else:
        # a file integrity check should be done outside
        return file_cont

def ck_forcefield(_ff_file_):
    '''
    podria pedirse solo este archivo y 
    de aqui sacar la iformacion de los otros dos....
    '''
    _flag_ = False
    comb_rule = -1
    with open(_ff_file_, 'r')  as indata:
        for j_line in indata:
            line_c = j_line.split()
            if j_line.startswith('[ defaults ]'):
                _flag_ = True
            if len(line_c)>1 and 'fudgeQQ'==line_c[-1]:
                j_line = indata.next()
                comb_rule= j_line.split()
                print('---> comb_rule {}'.format(comb_rule[1]))
                
            
    if comb_rule<0 or not _flag_:
        pop_err_1('forcefield.itp file is missing or incomplete')
        return 0, 0
    else:
        return comb_rule, _flag_

def get_top_groups(_mtype_container_, _group_):
    
    _mtype_ = _mtype_container_
    _buffer = []
    for mt in range(len( _mtype_)):
        
        mtype = _mtype_[mt].strip(' ')
        if _buffer==[] and mtype==_group_:
            buffer = [ mtype, mt+1]
            
        elif _buffer<>[] and mtype<>_group_:
            _buffer += [mt]
            break
            
        elif mt==(len(_mtype_)-1):
            
            _buffer += [mt+1]
                
    print''
    print 'Group characterized as: {} with ids {} to {}'.format(*_buffer)
    return _buffer


if __name__ == '__main__':
    
    pass
    
