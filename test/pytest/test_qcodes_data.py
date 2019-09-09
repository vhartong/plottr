import numpy as np
import qcodes as qc
from qcodes import initialise_database, load_or_create_experiment

from plottr.data.datadict import DataDict
from plottr.utils import testdata
from plottr.node.tools import linearFlowchart
from plottr.data.qcodes_dataset import (
    datadict_from_path_and_run_id,
    QCodesDSLoader,
    get_ds_structure,
    get_ds_info,
    get_runs_from_db)

DBPATH = './test_qc_saveandload.db'


def test_load_2dsoftsweep():
    qc.config.core.db_location = DBPATH
    initialise_database()
    exp = load_or_create_experiment('2d_softsweep', sample_name='no sample')

    N = 5
    m = qc.Measurement(exp=exp)
    m.register_custom_parameter('x', unit='cm')
    m.register_custom_parameter('y')

    # check that unused parameters don't mess with
    m.register_custom_parameter('foo')
    dd_expected = DataDict(x=dict(values=np.array([]), unit='cm'),
                           y=dict(values=np.array([])))
    for n in range(N):
        m.register_custom_parameter(f'z_{n}', setpoints=['x', 'y'])
        dd_expected[f'z_{n}'] = dict(values=np.array([]), axes=['x', 'y'])
    dd_expected.validate()

    with m.run() as datasaver:
        for result in testdata.generate_2d_scalar_simple(3, 3, N):
            row = [(k, v) for k, v in result.items()] + [('foo', 1)]
            datasaver.add_result(*row)
            dd_expected.add_data(**result)

    # retrieve data as data dict
    run_id = datasaver.dataset.captured_run_id
    ddict = datadict_from_path_and_run_id(DBPATH, run_id)
    assert ddict == dd_expected


def test_get_ds_structure():
    qc.config.core.db_location = DBPATH
    initialise_database()
    exp = load_or_create_experiment('2d_softsweep', sample_name='no sample')

    N = 5

    m = qc.Measurement(exp=exp)
    m.register_custom_parameter('x', unit='cm')
    m.register_custom_parameter('y')

    # check that unused parameters don't mess with
    m.register_custom_parameter('foo')

    for n in range(N):
        m.register_custom_parameter(f'z_{n}', setpoints=['x', 'y'])

    with m.run() as datasaver:
        dataset = datasaver.dataset

    # test dataset structure function
    expected_structure = {
        'x': {
            'unit': 'cm',
            'values': []
        },
        'y': {
            'unit': '',
            'values': []
        }
        # note that parameter 'foo' is not expected to be included
        # because it's a "standalone" parameter
    }
    for n in range(N):
        expected_structure.update(
            {f'z_{n}': {
                'unit': '',
                'axes': ['x', 'y'],
                'values': []
                }
            }
        )
    structure = get_ds_structure(dataset)
    assert structure == expected_structure


def test_get_ds_info():
    qc.config.core.db_location = DBPATH
    initialise_database()
    exp = load_or_create_experiment('test_get_ds_info', sample_name='qubit')

    N = 5

    m = qc.Measurement(exp=exp)

    m.register_custom_parameter('x', unit='cm')
    m.register_custom_parameter('y')
    m.register_custom_parameter('foo')
    for n in range(N):
        m.register_custom_parameter(f'z_{n}', setpoints=['x', 'y'])

    with m.run() as datasaver:
        dataset = datasaver.dataset

        ds_info_with_empty_timestamps = get_ds_info(dataset,
                                                    get_structure=False)
        assert ds_info_with_empty_timestamps['completed date'] == ''
        assert ds_info_with_empty_timestamps['completed time'] == ''

    # timestamps are difficult to test for, so we will cheat here and
    # instead of hard-coding timestamps we will just get them from the dataset
    started_ts = dataset.run_timestamp()
    completed_ts = dataset.completed_timestamp()

    expected_ds_info = {
        'experiment': 'test_get_ds_info',
        'sample': 'qubit',
        'completed date': completed_ts[:10],
        'completed time': completed_ts[11:],
        'started date': started_ts[:10],
        'started time': started_ts[11:],
        'records': 0
    }

    ds_info = get_ds_info(dataset, get_structure=False)

    assert ds_info == expected_ds_info

    expected_ds_info_with_structure = expected_ds_info.copy()
    expected_ds_info_with_structure['structure'] = get_ds_structure(dataset)

    ds_info_with_structure = get_ds_info(dataset)

    assert ds_info_with_structure == expected_ds_info_with_structure


def test_get_runs_from_db(tmp_path):
    # Prepare datasets

    db_path = str(tmp_path / 'some.db')
    qc.config.core.db_location = db_path
    initialise_database()

    exp1 = load_or_create_experiment('get_runs_from_db', sample_name='qubit')
    m1 = qc.Measurement(exp=exp1)

    m1.register_custom_parameter('x', unit='cm')
    m1.register_custom_parameter('y')
    m1.register_custom_parameter('foo')
    for n in range(2):
        m1.register_custom_parameter(f'z_{n}', setpoints=['x', 'y'])

    with m1.run() as datasaver:
        dataset11 = datasaver.dataset

    with m1.run() as datasaver:
        datasaver.add_result(('x', 1.), ('y', 2.), ('z_0', 42.), ('z_1', 0.2))

        dataset12 = datasaver.dataset

    exp2 = load_or_create_experiment('give_em', sample_name='now')
    m2 = qc.Measurement(exp=exp2)

    m2.register_custom_parameter('a')
    m2.register_custom_parameter('b', unit='mm')
    m2.register_custom_parameter('c', setpoints=['a', 'b'])

    with m2.run() as datasaver:
        datasaver.add_result(('a', 1.), ('b', 2.), ('c', 42.))
        datasaver.add_result(('a', 4.), ('b', 5.), ('c', 77.))
        dataset2 = datasaver.dataset

    # Prepare an expected overview of the created database
    expected_overview = {ds.run_id: get_ds_info(ds, get_structure=False)
                         for ds in (dataset11, dataset12, dataset2)}

    # Get the actual overview of the created database
    overview = get_runs_from_db(db_path)

    # Finally, assert
    assert overview == expected_overview

    # Prepare an expected overview of the created database WITH STRUCTURE
    expected_overview_with_structure = {
        ds.run_id: get_ds_info(ds, get_structure=True)
        for ds in (dataset11, dataset12, dataset2)
    }

    # Get the actual overview of the created database WITH STRUCTURE
    overview_with_structure = get_runs_from_db(db_path, get_structure=True)

    # Finally, assert WITH STRUCTURE
    assert overview_with_structure == expected_overview_with_structure


def test_update_qcloader(qtbot):
    qc.config.core.db_location = DBPATH
    initialise_database()
    exp = load_or_create_experiment('2d_softsweep', sample_name='no sample')

    N = 2
    m = qc.Measurement(exp=exp)
    m.register_custom_parameter('x')
    m.register_custom_parameter('y')
    dd_expected = DataDict(x=dict(values=np.array([])),
                           y=dict(values=np.array([])))
    for n in range(N):
        m.register_custom_parameter(f'z_{n}', setpoints=['x', 'y'])
        dd_expected[f'z_{n}'] = dict(values=np.array([]), axes=['x', 'y'])
    dd_expected.validate()

    # setting up the flowchart
    fc = linearFlowchart(('loader', QCodesDSLoader))
    loader = fc.nodes()['loader']

    def check():
        nresults = ds.number_of_results
        loader.update()
        ddict = fc.output()['dataOut']

        if ddict is not None and nresults > 0:
            z_in = dd_expected.data_vals('z_1')
            z_out = ddict.data_vals('z_1')
            if z_out is not None:
                assert z_in.size == z_out.size
                assert np.allclose(z_in, z_out, atol=1e-15)

    with m.run() as datasaver:
        ds = datasaver.dataset
        run_id = datasaver.dataset.captured_run_id
        loader.pathAndId = DBPATH, run_id

        for result in testdata.generate_2d_scalar_simple(3, 3, N):
            row = [(k, v) for k, v in result.items()]
            datasaver.add_result(*row)
            dd_expected.add_data(**result)
            check()
        check()

    # insert data in small chunks, and check
    # while True:
    #     try:
    #         ninsertions = np.random.randint(0, 5)
    #         for n in range(ninsertions):
    #             _ds.add_result(next(results))
    #     except StopIteration:
    #         _ds.mark_complete()
    #         break
    #     check()
    # check()
